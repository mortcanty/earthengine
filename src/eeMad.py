import ee

def covarw(image, weights, maxPixels=1e9):
    '''Return the weighted centered image and its weighted covariance matrix'''  
    geometry = image.geometry()
    bandNames = image.bandNames()
    N = bandNames.length()
    scale = image.select(0).projection().nominalScale()
    weightsImage = image.multiply(ee.Image.constant(0)).add(weights)
    means = image.addBands(weightsImage) \
                 .reduceRegion(ee.Reducer.mean().repeat(N).splitWeights(), scale=scale,maxPixels=maxPixels) \
                 .toArray() \
                 .project([1])
    centered = image.toArray().subtract(means) 
    B1 = centered.bandNames().get(0)       
    b1 = weights.bandNames().get(0)     
    nPixels = ee.Number(centered.reduceRegion(ee.Reducer.count(), scale=scale, maxPixels=maxPixels).get(B1)) 
    sumWeights = ee.Number(weights.reduceRegion(ee.Reducer.sum(),geometry=geometry, scale=scale, maxPixels=maxPixels).get(b1))
    covw = centered.multiply(weights.sqrt()) \
                   .toArray() \
                   .reduceRegion(ee.Reducer.centeredCovariance(), geometry=geometry, scale=scale, maxPixels=maxPixels) \
                   .get('array')
    covw = ee.Array(covw).multiply(nPixels).divide(sumWeights)
    return (centered.arrayFlatten([bandNames]), covw)

def chi2cdf(chi2,df):
    ''' Chi square cumulative distribution function '''
    return ee.Image(chi2.divide(2)).gammainc(ee.Number(df).divide(2))

def geneiv(C,B):
    ''' Generalized eigenproblem C*X = lambda*B*X '''
    C = ee.Array(C)
    B = ee.Array(B)  
#  Li = choldc(B)^-1
    Li = ee.Array(B.matrixCholeskyDecomposition().get('L')).matrixInverse()
#  solve symmetric eigenproblem Li*C*Li^T*x = lambda*x
    Xa = Li.matrixMultiply(C) \
           .matrixMultiply(Li.matrixTranspose()) \
           .eigen()
#  eigenvalues as a row vector
    lambdas = Xa.slice(1,0,1).matrixTranspose()
#  eigenvectors as columns
    X = Xa.slice(1,1).matrixTranspose()  
#  generalized eigenvectors as columns, Li^T*X
    eigenvecs = Li.matrixTranspose().matrixMultiply(X)
    return (lambdas,eigenvecs) 

def addcoeffs(current,prev):
    coeff = ee.List(current)
    log = ee.List(prev)
    return log.add(coeff)

def radcalbatch(current,prev):  
    ''' Batch radiometric normalization '''  
    prev = ee.Dictionary(prev)
    target = ee.Image(current)    
    reference = ee.Image(prev.get('reference'))
    normalizedimages = ee.List(prev.get('normalizedimages'))
    niter = ee.Number(prev.get('niter'))
    rect = ee.Geometry(prev.get('rect'))
    log = ee.List(prev.get('log'))
    nbands = reference.bandNames().length()
#  clip the images to subset and run iMAD    
    inputlist = ee.List.sequence(1,niter)
    image = reference.addBands(target)
    first = ee.Dictionary({'done':ee.Number(0),
                           'image':image.clip(rect),
                           'allrhos': [ee.List.sequence(1,nbands)],
                           'chi2':ee.Image.constant(0),
                           'MAD':ee.Image.constant(0)})         
    result = ee.Dictionary(inputlist.iterate(imad,first))                
    chi2 = ee.Image(result.get('chi2')).rename(['chi2'])
    allrhos = ee.List(result.get('allrhos'))
#  run radcal     
    ncmask = chi2cdf(chi2,nbands).lt(ee.Image.constant(0.05))                     
    inputlist1 = ee.List.sequence(0,nbands.subtract(1))
    first = ee.Dictionary({'image':image,
                           'ncmask':ncmask,
                           'nbands':nbands,
                           'rect':rect,
                           'coeffs': ee.List([]),
                           'normalized':ee.Image()})
    result = ee.Dictionary(inputlist1.iterate(radcal,first))          
    coeffs = ee.List(result.get('coeffs')) 
#  update log    
    ninvar = ee.String(ncmask.reduceRegion(ee.Reducer.sum().unweighted(),maxPixels= 1e9).toArray().project([0]))
    log = log.add(target.get('system:id'))
    iters = allrhos.length().subtract(1)
    log = log.add(ee.Algorithms.If(iters.eq(niter),['No convergence, iterations:',iters], 
                                                   ['Iterations:',iters]))
    log = log.add(['Invariant pixels:',ninvar])
    log = ee.List(coeffs.iterate(addcoeffs,log)) 
#  first band in normalized result is empty                
    sel = ee.List.sequence(1,nbands)
    normalized = ee.Image(result.get('normalized')).select(sel)
    normalizedimages = normalizedimages.add(normalized)  
    return ee.Dictionary({'reference':reference,'rect':rect,'niter':niter,'log':log,'normalizedimages':normalizedimages})     

def radcal(current,prev):
    ''' iterator function for orthogonal regression and interactive radiometric normalization '''
    k = ee.Number(current)
    prev = ee.Dictionary(prev)    
#  image is concatenation of reference and target    
    image = ee.Image(prev.get('image'))
    ncmask = ee.Image(prev.get('ncmask'))
    nbands = ee.Number(prev.get('nbands'))
    rect = ee.Geometry(prev.get('rect'))
    coeffs = ee.List(prev.get('coeffs'))
    normalized = ee.Image(prev.get('normalized'))
    scale = image.select(0).projection().nominalScale()
#  orthoregress reference onto target  
    image1 = image.clip(rect).select(k.add(nbands),k).updateMask(ncmask).rename(['x','y'])
    means = image1.reduceRegion(ee.Reducer.mean(), scale=scale, maxPixels=1e9) \
                  .toArray()\
                  .project([0])              
    Xm = means.get([0])    
    Ym = means.get([1])    
    S = ee.Array(image1.toArray() \
                       .reduceRegion(ee.Reducer.covariance(), geometry=rect, scale=scale, maxPixels=1e9) \
                       .get('array'))     
#  Pearson correlation     
    R = S.get([0,1]).divide(S.get([0,0]).multiply(S.get([1,1])).sqrt())
    eivs = S.eigen()
    e1 = eivs.get([0,1])
    e2 = eivs.get([0,2])
#  slope and intercept    
    b = e2.divide(e1)
    a = Ym.subtract(b.multiply(Xm))
    coeffs = coeffs.add(ee.List([b,a,R]))
#  normalize kth band in target    
    normalized = normalized.addBands(image.select(k.add(nbands)).multiply(b).add(a))
    return ee.Dictionary({'image':image,'ncmask':ncmask,'nbands':nbands,'rect':rect,'coeffs':coeffs,'normalized':normalized})    

def imad(current,prev):
    done =  ee.Number(ee.Dictionary(prev).get('done'))
    return ee.Algorithms.If(done,prev,imad1(current,prev))

def imad1(current,prev): 
    ''' Iteratively re-weighted MAD '''
    image = ee.Image(ee.Dictionary(prev).get('image'))
    chi2 = ee.Image(ee.Dictionary(prev).get('chi2'))      
    allrhos = ee.List(ee.Dictionary(prev).get('allrhos'))
    region = image.geometry()   
    nBands = image.bandNames().length().divide(2) 
    weights = chi2cdf(chi2,nBands).subtract(1).multiply(-1)
    centeredImage,covarArray = covarw(image,weights)
    bNames = centeredImage.bandNames()
    bNames1 = bNames.slice(0,nBands)
    bNames2 = bNames.slice(nBands)
    centeredImage1 = centeredImage.select(bNames1)
    centeredImage2 = centeredImage.select(bNames2) 
    s11 = covarArray.slice(0,0,nBands).slice(1,0,nBands)
    s22 = covarArray.slice(0,nBands).slice(1,nBands)
    s12 = covarArray.slice(0,0,nBands).slice(1,nBands)
    s21 = covarArray.slice(0,nBands).slice(1,0,nBands)      
    c1 = s12.matrixMultiply(s22.matrixInverse()).matrixMultiply(s21)
    b1 = s11
    c2 = s21.matrixMultiply(s11.matrixInverse()).matrixMultiply(s12)
    b2 = s22
#  solution of generalized eigenproblems     
    lambdas, A = geneiv(c1,b1)
    _,       B = geneiv(c2,b2) 
    rhos = lambdas.sqrt().project(ee.List([1]))
#  test for convergence    
    lastrhos = ee.Array(allrhos.get(-1))
    done = rhos.subtract(lastrhos) \
               .abs() \
               .reduce(ee.Reducer.max(),ee.List([0])) \
               .lt(ee.Number(0.001)) \
               .toList() \
               .get(0)       
    allrhos = allrhos.cat([rhos.toList()]) 
#  MAD variances    
    sigma2s = rhos.subtract(1).multiply(-2).toList() 
    sigma2s = ee.Image.constant(sigma2s)
#  ensure sum of positive correlations between X and U is positive
    tmp = s11.matrixDiagonal().sqrt()
    ones = tmp.multiply(0).add(1)
    tmp = ones.divide(tmp).matrixToDiag()
    s = tmp.matrixMultiply(s11).matrixMultiply(A).reduce(ee.Reducer.sum(),[0]).transpose()
    A = A.matrixMultiply(s.divide(s.abs()).matrixToDiag())
#  ensure positive correlation
    tmp = A.transpose().matrixMultiply(s12).matrixMultiply(B).matrixDiagonal()
    tmp = tmp.divide(tmp.abs()).matrixToDiag()
    B = B.matrixMultiply(tmp)           
#  canonical and MAD variates 
    centeredImage1Array = centeredImage1.toArray().toArray(1)
    centeredImage2Array = centeredImage2.toArray().toArray(1)
    U = ee.Image(A.transpose()).matrixMultiply(centeredImage1Array) \
                   .arrayProject([0]) \
                   .arrayFlatten([bNames1])
    V = ee.Image(B.transpose()).matrixMultiply(centeredImage2Array) \
                   .arrayProject([0]) \
                   .arrayFlatten([bNames2])   
    MAD = U.subtract(V)
#  chi square image
    chi2 = MAD.pow(2) \
              .divide(sigma2s) \
              .reduce(ee.Reducer.sum()) \
              .clip(region)                
    return ee.Dictionary({'done':done,'image':image,'allrhos':allrhos,'chi2':chi2,'MAD':MAD})     
    
if __name__ == '__main__': 
    pass
 



 