'''
Created on 09.01.2017

@author: mort
'''

import ee
from eeMad import chi2cdf

def multbyenl(image):
    return ee.Image(image).multiply(4.9)

def log_det_sum(imList,j):
    '''return the log of the the determinant of the sum of the first j images in imList'''
    def sumimgs(current,prev):
        return ee.Image(prev).add(current)
    first = ee.Image(ee.List(imList).get(0))
    nbands = first.bandNames().length()
    return ee.Algorithms.If(nbands.eq(2),  
        ee.Image(ee.List(imList).slice(1,j).iterate(sumimgs,first)).expression('b(0)*b(1)').log(),
        ee.Image(ee.List(imList).slice(1,j).iterate(sumimgs,first)).log() )
    
def log_det(imList,j):
    '''return the log of the the determinant of the jth image in imList'''
    im = ee.Image(ee.List(imList).get(j.subtract(1)))
    nbands = im.bandNames().length()
    return ee.Algorithms.If(nbands.eq(2),  
        ee.Image(im.expression('b(0)*b(1)')).log(),
        ee.Image(im).log() )
    
def pv(imList,p,median,j):
    ''' calculate -2log(R_ell,j) and return P-value '''
    imList = ee.List(imList).slice(0,j)
    p = ee.Number(p)
    Z = ee.Image(ee.Image(log_det_sum(imList,j.subtract(1)))).multiply(j.subtract(1)) \
                 .add(log_det(imList,j))  \
                 .add(p.multiply(j).multiply(ee.Number(j).log())) \
                 .subtract(p.multiply(j.subtract(1)).multiply(j.subtract(1).log())) \
                 .subtract(ee.Image(log_det_sum(imList,j)).multiply(j)) \
                 .multiply(-2*4.9)
    P = ee.Image(ee.Algorithms.If(p.eq(2),chi2cdf(Z,2),chi2cdf(Z,1)))
    return ee.Algorithms.If(median,
                 P.focal_median(1.5,'square','pixels',1),
                 P)

def pv_iter(current,prev):
    prev = ee.Dictionary(prev)
    median = prev.get('median')
    p = prev.get('p')
    imList = ee.List(prev.get('imList'))
    pvs = ee.List(prev.get('pvs'))
    j = ee.Number(current)
    return ee.Dictionary({'median':median,'p':p,'imList':imList,'pvs':pvs.add(pv(imList,p,median,j))})   

def smap_iter(current,prev):
    P = ee.Image(current)
    prev = ee.Dictionary(prev)
    j = ee.Number(prev.get('j'))
    threshold = ee.Image(prev.get('threshold'))
    smap = ee.Image(prev.get('smap'))
    smapj = smap.multiply(0).add(j)
    smap = smap.where(P.gt(threshold).And(smap.eq(0)),smapj)
    return ee.Dictionary({'j':j.add(1),'threshold':threshold,'smap':smap})

def omnibus(imList,significance=0.0001,median=False):
    '''return change maps for sequential omnibus change algorithm'''
    imList = ee.List(imList).map(multbyenl)    
    p = ee.Image(imList.get(0)).bandNames().length()
    k = imList.length()
    
#  test for ell = 1  
    ell = ee.Number(1)  
    js = ee.List.sequence(ell.add(1),k)    
    first = ee.Dictionary({'median':median,'p':p,'imList':imList,'pvs':ee.List([])})
#  list of P-values for R_ell,j, j = ell+1...k    
    pvs = ee.List(ee.Dictionary(
            js.iterate(pv_iter,first)
                       ).get('pvs'))
#  smap
    smap = ee.Image(imList.get(0)).select(0).multiply(0.0)  
    threshold = ee.Image.constant(1-significance)
    first = ee.Dictionary({'j':1,'threshold':threshold,'smap':smap})                       
    smap = ee.Dictionary(pvs.iterate(smap_iter,first)).get('smap')
    
    return (None,smap,None,None)

if __name__ == '__main__':
    pass