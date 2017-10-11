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
    imList = ee.List(imList)
    nbands = ee.Image(imList.get(0)).bandNames().length() 
    sumj = ee.ImageCollection(imList.slice(0,j)).reduce(ee.Reducer.sum())
    return ee.Algorithms.If( nbands.eq(2),                         
        sumj.expression('b(0)*b(1)').log(),
        sumj.log() )                    
    
def log_det(imList,j):
    '''return the log of the the determinant of the jth image in imList'''
    im = ee.Image(ee.List(imList).get(j.subtract(1)))
    nbands = im.bandNames().length()
    return ee.Algorithms.If(nbands.eq(2),  
        im.expression('b(0)*b(1)').log(),
        im.log() )
    
def pv(imList,p,median,j):
    ''' calculate -2log(R_ell,j) and return P-value '''
    imList = ee.List(imList)
    p = ee.Number(p)
    j = ee.Number(j)
    f = p
    one = ee.Number(1.0)
# 1 - (1. + 1./(j*(j-1)))/(6.*p*n)    
    rhoj = one.subtract(one.add(one.divide(j.multiply(j.subtract(one)))).divide(6*4.9))
# -(f/4.)*(1.-1./rhoj)**2'    
    omega2j = one.subtract(one.divide(rhoj)).pow(2.0).multiply(f.divide(-4.0))
    Z = ee.Image(ee.Image(log_det_sum(imList,j.subtract(1)))).multiply(j.subtract(1)) \
                 .add(log_det(imList,j))  \
                 .add(p.multiply(j).multiply(ee.Number(j).log())) \
                 .subtract(p.multiply(j.subtract(1)).multiply(j.subtract(1).log())) \
                 .subtract(ee.Image(log_det_sum(imList,j)).multiply(j)) \
                 .multiply(rhoj) \
                 .multiply(-2*4.9)
# (1.-omega2j)*stats.chi2.cdf(Z,[f])+omega2j*stats.chi2.cdf(Z,[f+4])                 
    P = ee.Image( chi2cdf(Z,f).multiply(one.subtract(omega2j)).add(chi2cdf(Z,f.add(4)).multiply(omega2j))  )
# 3x3 median filter    
    return ee.Algorithms.If(median, P.focal_median(), P)    

def js_iter(current,prev):
    j = ee.Number(current)
    prev = ee.Dictionary(prev)
    median = prev.get('median')
    p = prev.get('p')
    imList = prev.get('imList')
    pvs = ee.List(prev.get('pvs'))  
    return ee.Dictionary({'median':median,'p':p,'imList':imList,'pvs':pvs.add(pv(imList,p,median,j))})   

def ells_iter(current,prev):
    ell = ee.Number(current)
    prev = ee.Dictionary(prev)
    pv_arr = ee.List(prev.get('pv_arr'))
    k = ee.Number(prev.get('k'))
    median = prev.get('median')
    p = prev.get('p')
    imList = ee.List(prev.get('imList'))
    imList_ell = imList.slice(ell.subtract(1))
    js = ee.List.sequence(2,k.subtract(ell).add(1))
    first = ee.Dictionary({'median':median,'p':p,'imList':imList_ell,'pvs':ee.List([])})
#  list of P-values for R_ell,j, j = 2...k-ell+1    
    pvs = ee.List(ee.Dictionary(js.iterate(js_iter,first)).get('pvs'))
    return ee.Dictionary({'k':k,'p':p,'median':median,'imList':imList,'pv_arr':pv_arr.add(pvs)})

def filter_j(current,prev):
    P = ee.Image(current)
    prev = ee.Dictionary(prev)
    ell = ee.Number(prev.get('ell'))
    cmap = ee.Image(prev.get('cmap'))
    smap = ee.Image(prev.get('smap'))
    fmap = ee.Image(prev.get('fmap'))
    bmap = ee.Image(prev.get('bmap'))
    threshold = ee.Image(prev.get('threshold'))
    j = ee.Number(prev.get('j'))
    cmapj = cmap.multiply(0).add(ell.add(j).subtract(1))
    cmap1 = cmap.multiply(0).add(1)
    tst = P.gt(threshold).And(cmap.eq(ell.subtract(1)))
    cmap = cmap.where(tst,cmapj)
    fmap = fmap.where(tst,fmap.add(1))
    smap = ee.Algorithms.If(ell.eq(1),smap.where(tst,cmapj),smap)
    idx = ell.add(j).subtract(2)
    tmp = bmap.select(idx)
    bname = bmap.bandNames().get(idx)
    tmp = tmp.where(tst,cmap1)
    tmp = tmp.rename([bname])    
    bmap = bmap.addBands(tmp,[bname],True)    
    return ee.Dictionary({'ell':ell,'j':j.add(1),'threshold':threshold,'cmap':cmap,'smap':smap,'fmap':fmap,'bmap':bmap})

def filter_ell(current,prev):
    pvs = ee.List(current)
    prev = ee.Dictionary(prev)
    ell = ee.Number(prev.get('ell'))
    threshold = ee.Image(prev.get('threshold'))
    cmap = prev.get('cmap')
    smap = prev.get('smap')
    fmap = prev.get('fmap')
    bmap = prev.get('bmap')
    first = ee.Dictionary({'ell':ell,'j':1, 'threshold':threshold,'cmap':cmap,'smap':smap,'fmap':fmap,'bmap':bmap}) 
    result = ee.Dictionary(ee.List(pvs).iterate(filter_j,first))
    return ee.Dictionary({'ell':ell.add(1),'threshold':threshold,'cmap':result.get('cmap'),
                                                                 'smap':result.get('smap'),
                                                                 'fmap':result.get('fmap'),
                                                                 'bmap':result.get('bmap')})

def omnibus(imList,significance=0.0001,median=False):
    '''return change maps for sequential omnibus change algorithm'''    
    imList = ee.List(imList).map(multbyenl)    
    p = ee.Image(imList.get(0)).bandNames().length()
    k = imList.length() 
#  pre-calculate p-value array    
    ells = ee.List.sequence(1,k.subtract(1))
    first = ee.Dictionary({'k':k,'p':p,'median':median,'imList':imList,'pv_arr':ee.List([])})
    pv_arr = ee.List(ee.Dictionary(ells.iterate(ells_iter,first)).get('pv_arr'))      
#  filter p-values to generate cmap, smap, fmap and bmap
    cmap = ee.Image(imList.get(0)).select(0).multiply(0.0)
    smap = ee.Image(imList.get(0)).select(0).multiply(0.0)
    fmap = ee.Image(imList.get(0)).select(0).multiply(0.0)   
    bmap = ee.Image.constant(ee.List.repeat(0,k.subtract(1)))    
    threshold = ee.Image.constant(1-significance)
    first = ee.Dictionary({'ell':1,'threshold':threshold,'cmap':cmap,'smap':smap,'fmap':fmap,'bmap':bmap})
    return ee.Dictionary(pv_arr.iterate(filter_ell,first)) 

if __name__ == '__main__':
    pass