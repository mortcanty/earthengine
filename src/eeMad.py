import ee

def covarw(image, weights, scale=30, maxPixels=1e9):
    '''Return the weighted centered image and its weighted covariance matrix'''  
    geometry = image.geometry()
    bandNames = image.bandNames()
    N = bandNames.length()
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
#  sort in increasing order
    keys = ee.List.sequence(nBands,1,-1)   
    A = A.sort([keys])
    B = B.sort([keys]) 
    rhos = rhos.sort(keys) 
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
    pass
#  ensure positive correlation
    tmp = A.transpose().matrixMultiply(s12).matrixMultiply(B).matrixDiagonal()
    tmp = tmp.divide(tmp.abs()).matrixToDiag()
    B = B.matrixMultiply(tmp)  
          
# # -------------------------------------------------------------------
#     s11 = np.mat(s11.getInfo())    
#     s12 = np.mat(s12.getInfo())          
#     A = np.mat(A.getInfo())
#     B = np.mat(B.getInfo())    
# #  ensure sum of positive correlations between X and U is positive
#     tmp = np.diag(1/np.sqrt(np.diag(s11)))  
#     s = np.ravel(np.sum(tmp*s11*A,axis=0)) 
#     A = A*np.diag(s/np.abs(s))                                    
# #  ensure positive correlation
#     tmp = np.diag(A.T*s12*B)
#     B = B*np.diag(tmp/abs(tmp))   
#     A = ee.Array(A.tolist())
#     B = ee.Array(B.tolist())  
# # -------------------------------------------------------------------    
                   
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
#  no-change probability                
              
    return ee.Dictionary({'done':done,'image':image,'allrhos':allrhos,'chi2':chi2,'MAD':MAD})     
    
if __name__ == '__main__': 
    pass
 



 