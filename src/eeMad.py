import ee

def dataArray(image, maxPixels=1e9):
    '''Return image as a data array'''
    nBands = image.bandNames().length()
    return ee.Array(image \
                    .reduceRegion(ee.Reducer.toList(nBands), maxPixels=maxPixels) \
                    .get('list'))

def centerw(image, weights=None, maxPixels=1e9):
    '''Return a (weighted) centered image'''
    if weights==None:
        weights = ee.Image.constant(1)
    B1 = image.bandNames().get(0)
    mask = image.select(ee.String(B1)).mask()
    nPixels = ee.Number(image.reduceRegion(ee.Reducer.count(), maxPixels=maxPixels).get(B1))
    b1 = weights.bandNames().get(0)
    weights = weights.updateMask(mask)     
    sumWeights = ee.Number(weights.reduceRegion(ee.Reducer.sum(), maxPixels=maxPixels).get(b1)) 
    meanDict = image.multiply(weights) \
        .reduceRegion(ee.Reducer.mean(), maxPixels=maxPixels)   
    meanImage = meanDict.toImage(meanDict.keys()).multiply(nPixels.divide(sumWeights))         
    return image.subtract(meanImage)

def covw(centeredImage, weights=None, maxPixels=1e9):
    '''Return the (weighted) covariance matrix of a centered image''' 
    if weights==None:
        weights = centeredImage.multiply(0).add(ee.Image.constant(1))           
    B1 = centeredImage.bandNames().get(0)       
    b1 = weights.bandNames().get(0)     
    sumWeights = ee.Number(weights.reduceRegion(ee.Reducer.sum(), maxPixels=maxPixels).get(b1))  
    nPixels = ee.Number(centeredImage.reduceRegion(ee.Reducer.count(), maxPixels=maxPixels).get(B1))   
#    arr = dataArray(centeredImage.multiply(weights.sqrt()))
#    return arr.matrixTranspose().matrixMultiply(arr).divide(sumWeights)
    covW = centeredImage \
        .multiply(weights.sqrt()) \
        .toArray() \
        .reduceRegion(ee.Reducer.centeredCovariance(), maxPixels=1e9) \
        .get('array')
    return ee.Array(covW).multiply(nPixels.divide(sumWeights)) 

def chi2cdf(chi2,df):
    df = ee.Image.constant(ee.Number(df).divide(2))
    return ee.Image(chi2.divide(2)).gammainc(df)

def chi2cdf_old(chi2,df):
    '''Return the chi-square cdf of chi2 image
       (From Charles Morton's JavaScript code)'''   
    def gser(img,prev):
#      series approximation to incomplete gamma
#      converges quickly for x < a+1 (Numerical Recipes, Eq. 6.2.5)        
        x = ee.Image(img).select(['x'])
        a = ee.Image(img).select(['a'])
        g_prev = ee.Image(ee.Dictionary(prev).get('g'))
        n = ee.Number(ee.Dictionary(prev).get('n'))
        return ee.Dictionary({
              'g': g_prev.add(x.pow(n).divide(a.add(n).add(1).gamma())),
              'n': n.add(1)})       
    def gcf(inpt,prev):
#      continued fraction approximation to incomplete gamma
#      converges quickly for x > a+1 (Numerical Recipes, Eq. 6.2.6)           
        n = ee.Number(inpt);
        b = ee.Image(ee.Dictionary(prev).get('b'))
        c = ee.Image(ee.Dictionary(prev).get('c'))
        d = ee.Image(ee.Dictionary(prev).get('d'))
        h = ee.Image(ee.Dictionary(prev).get('h'))        
        an = a.subtract(n).multiply(n)
        b = b.add(2.0)
#      This is slightly different than in the recipe
#      Can c and d go negative?
        c = an.divide(c).add(b).abs().max(FPMIN)
        d = an.multiply(d).add(b).abs().max(FPMIN).pow(-1)
        h = h.multiply(c.multiply(d))
        return ee.Dictionary({'b': b, 'c': c, 'd': d, 'h': h})   
    df = ee.Number(df)     
    FPMIN = ee.Number(1.0e-30)
    n_max1 = 5
    n_max2 = 5    
    input_img = ee.Image.cat(chi2.divide(ee.Image.constant(2.0)),ee.Image.constant(df.divide(2.0))).rename(['x','a']) 
    x = input_img.select(['x']);
    a = input_img.select(['a']);
#  mask with 1 where gser is valid, 0 where gcf is valid     
    mask = x.lt(ee.Image.constant(df.divide(2.0).add(1.0)))
#  first get chi2cdf valid for ch2 < df/2 + 1    
    first = ee.Dictionary({'g': a.multiply(0), 'n': 0})
    chi2cdf1 = ee.Image(ee.Dictionary(ee.List.repeat(input_img, n_max1) \
              .iterate(gser, first)).get('g')) \
              .multiply(x.multiply(-1).exp()).multiply(x.pow(a))  
#  next get chi2cdf valid for chi2 > df/s + 1
    first = ee.Dictionary({'b':x.add(1.0).subtract(a),
                           'c':x.multiply(0).add(FPMIN).pow(-1),
                           'd':x.add(1.0).subtract(a).pow(-1),
                           'h':x.add(1.0).subtract(a).pow(-1)})
    gln = a.gamma().log()
#  Modified from recipe to calculate complement of result (P(a,x) instead of Q(a,x))    
    chi2cdf2 = ee.Image(ee.Dictionary(ee.List.sequence(1, n_max2).iterate(gcf, first)).get('h')) \
              .multiply(x.multiply(-1).add(x.log().multiply(a)).subtract(gln).exp()) \
              .multiply(-1).add(1)
#  return chi2cdf valid for all values of chi2               
    return chi2cdf2.where(mask,chi2cdf1)

def imad(current,prev): 
    import numpy as np
    from numpy import linalg 
    import auxil.auxil as auxil  

    image1 = ee.Image(ee.Dictionary(current).get('image1'))
    image2 = ee.Image(ee.Dictionary(current).get('image2'))
    weights = ee.Image(ee.Dictionary(prev).get('weights'))      
    region = image1.geometry()  
    bNames1 = image1.bandNames() 
    bNames2 = image2.bandNames() 
    nBands = len(bNames1.getInfo())  
    centeredImage1 = centerw(image1,weights) 
    centeredImage2 = centerw(image2,weights) 
    centeredImage = ee.Image.cat(centeredImage1,centeredImage2)                                
    covarArray = covw(centeredImage,weights)   
# -------- cannot be iterated!!! --------
    S = np.mat(covarArray.getInfo())
# ---------------------------------------    
    s11 = S[0:nBands,0:nBands]    
    s22 = S[nBands:,nBands:] 
    s12 = S[0:nBands,nBands:]
    s21 = S[nBands:,0:nBands]        
    c1 = s12*linalg.inv(s22)*s21 
    b1 = s11
    c2 = s21*linalg.inv(s11)*s12
    b2 = s22
#  solution of generalized eigenproblems 
    mu2a,A = auxil.geneiv(c1,b1)                
    mu2b,B = auxil.geneiv(c2,b2)                
#  sort a   
    idx = np.argsort(mu2a)      
    A = A[:,idx]        
#  sort b   
    idx = np.argsort(mu2b)
    B = B[:,idx]        
    mu2 = mu2b[idx]       
#  canonical correlations and MAD variances             
    rho = np.sqrt(mu2)        
    print rho        
    s2 = (2*(1-rho)).tolist()
    variance = ee.Image.constant(s2)
#  ensure sum of positive correlations between X and U is positive
    tmp = np.diag(1/np.sqrt(np.diag(s11)))  
    s = np.ravel(np.sum(tmp*s11*A,axis=0)) 
    A = A*np.diag(s/np.abs(s))                                    
#  ensure positive correlation
    tmp = np.diag(A.T*s12*B)
    B = B*np.diag(tmp/abs(tmp))                
#  canonical and MAD variates 
    Arr = ee.Array(A.tolist())
    Brr = ee.Array(B.tolist())
    centeredImage1Array = centeredImage1.toArray().toArray(1)
    centeredImage2Array = centeredImage2.toArray().toArray(1)
    U = ee.Image(Arr).matrixMultiply(centeredImage1Array) \
        .arrayProject([0]) \
        .arrayFlatten([bNames1])
    V = ee.Image(Brr).matrixMultiply(centeredImage2Array) \
        .arrayProject([0]) \
        .arrayFlatten([bNames2])   
    MAD = U.subtract(V)
#  chi square image
    chi2 = (MAD.pow(2)) \
            .divide(variance) \
            .reduce(ee.Reducer.sum()) \
            .clip(region)  
#  no-change probability                
    weights = ee.Image.constant(1.0).subtract(chi2cdf(chi2,6.0))        
    return ee.Dictionary({'weights':weights,'MAD':MAD})

if __name__ == '__main__': 
#  test      
    ee.Initialize()
    niter = 5
    image1 = ee.Image('users/mortcanty/aster1')
    image2 = ee.Image('users/mortcanty/aster2') 
    B1 = image1.bandNames().get(0)
    input_dict = ee.Dictionary({'image1':image1,'image2':image2}) 
    first = ee.Dictionary({'weights':image1.select(ee.String(B1)).multiply(0).add(ee.Image.constant(1)),
                           'MAD':ee.Image.constant(0)}) 
#  ----------iteration not yet possible--------------------------    
#    result = ee.List.repeat(input_dict, nMax).iterate(imad,first)
#  fake iteration:
    itr = 0
    while itr < niter: 
        result = imad(input_dict,first) 
        weights = result.get('weights')
        first = ee.Dictionary({'weights':weights,'MAD':ee.Image.constant(0)}) 
        itr += 1
 



 