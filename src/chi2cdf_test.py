import ee
from eeMad import  chi2cdf
from scipy.stats import chi2
import numpy as np

ee.Initialize()

x = 2
df = 5
 
print 'scipy:   ', chi2.cdf(x,df)
 
point = ee.Geometry.Point([50,6])
 
img = ee.Image.constant(x)
dfi = ee.Image.constant(df)
#result = chi2cdf_old(img,df)
result1 = chi2cdf(img,df)
 
print 'chi2cdf: ',result1.reduceRegion( ee.Reducer.first(), geometry = point, scale = 4000).getInfo()
 
arr = np.mat(np.random.randn(100,4))
cov = ee.Array((arr.T*arr).tolist())
print np.array(cov.getInfo())
 
L = ee.Array(cov.matrixCholeskyDecomposition().get('L'))
print np.array(L.getInfo())
 
S = L.matrixMultiply(L.matrixTranspose())
print np.array(S.getInfo())
 
S11 = S.slice(0,0,2).slice(1,0,2)
print np.array(S11.getInfo())
S22 = S.slice(0,2).slice(1,2)
print np.array(S22.getInfo())