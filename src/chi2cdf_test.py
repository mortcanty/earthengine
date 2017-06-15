import ee
from eeMad import chi2cdf_old, chi2cdf
from scipy.stats import chi2

ee.Initialize()

x = 2
df = 5

print 'scipy:   ', chi2.cdf(x,df)

point = ee.Geometry.Point([50,6])

img = ee.Image.constant(x)
dfi = ee.Image.constant(df)
result = chi2cdf_old(img,df)
result1 = chi2cdf(img,df)

print 'chi2cdf: ',result.reduceRegion( ee.Reducer.first(), geometry = point, scale = 4000).get('x').getInfo()

print 'gammainc: ',result1.reduceRegion( ee.Reducer.first(), geometry = point, scale = 4000).getInfo()