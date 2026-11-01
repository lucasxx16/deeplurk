import hashlib,json,sys,tarfile,time,warnings
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy.io import mmread
from scipy.sparse import save_npz
from scipy.sparse.csgraph import connected_components
import sklearn
from sklearn.neighbors import KNeighborsTransformer
from sklearn.cluster import SpectralClustering
from sklearn.metrics import adjusted_rand_score
import scanpy as sc
import anndata
import umap

start=time.monotonic();out=Path(__file__).resolve().parent;root=out.parent
src=root/'pbmc3k_filtered.tar.gz';prior=root/'P0370-pbmc3k-neighbors'
expected='847d6ebd9a1ec9a768f2be7e40ca42cbfe75ebeb6d76a4c24167041699dc28b5'
assert hashlib.sha256(src.read_bytes()).hexdigest()==expected
cells=pd.read_csv(prior/'neighbors.csv').cell_original_row.to_numpy()[:128]
genes=pd.read_csv(prior/'selected-genes.csv').gene_original_row.to_numpy()
assert len(cells)==128 and len(genes)==1000
with tarfile.open(src,'r:gz') as t:matrix=mmread(t.extractfile('filtered_gene_bc_matrices/hg19/matrix.mtx')).tocsr().astype(float)
sample=matrix[:,cells];depth=np.asarray(sample.sum(axis=0)).ravel();assert np.all(depth>0)
X=np.log1p(10000*sample[genes].toarray()/depth[None,:]).T
assert np.isfinite(X).all() and np.all(np.linalg.norm(X,axis=1)>0)
def sim(a,b): return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))
def distance(a,b): return 1-sim(a,b)
results={}; distgraphs={}; connectgraphs={}; labels={}
for name,metric in [('builtin','cosine'),('wrong_similarity',sim),('correct_distance',distance)]:
    captured=[]; got=[]
    try:
        adata=anndata.AnnData(X.copy())
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter('always')
            if name=='builtin': sc.pp.neighbors(adata,n_neighbors=15,n_pcs=0,metric=metric,random_state=370)
            else:
                transformer=KNeighborsTransformer(n_neighbors=15,metric=metric,n_jobs=1,algorithm='brute')
                sc.pp.neighbors(adata,n_neighbors=15,n_pcs=0,transformer=transformer,random_state=370)
            captured.extend(str(w.message) for w in got)
        d=adata.obsp['distances'].tocsr();c=adata.obsp['connectivities'].tocsr()
        assert d.shape==(128,128) and c.shape==(128,128) and np.isfinite(d.data).all() and np.isfinite(c.data).all()
        for label,g in [('distances',d),('connectivities',c)]:
            target=out/(name+'-'+label+'.npz')
            if target.exists():raise FileExistsError(target)
            save_npz(target,g)
        distgraphs[name]=d;connectgraphs[name]=c
        comp=int(connected_components(c,directed=False)[0])
        results[name]={'status':'ok','warnings':captured,'distance_nnz':int(d.nnz),'connectivity_nnz':int(c.nnz),'components':comp}
    except Exception as exc:
        if not captured: captured.extend(str(w.message) for w in got)
        results[name]={'status':'failed','warnings':captured,'error':type(exc).__name__+': '+str(exc)}

def rows(g):
    return [set(int(j) for j in g.indices[g.indptr[i]:g.indptr[i+1]] if j!=i) for i in range(g.shape[0])]
comparisons={}
for other in ('wrong_similarity','correct_distance'):
    if 'builtin' in distgraphs and other in distgraphs:
        a,b=rows(distgraphs['builtin']),rows(distgraphs[other])
        jac=[len(x&y)/len(x|y) if x|y else 1.0 for x,y in zip(a,b)]
        comparisons[other]={'distance_neighbor_jaccard_min_median_max':[float(np.min(jac)),float(np.median(jac)),float(np.max(jac))]}
for name,g in connectgraphs.items():
    try:
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter('always')
            labels[name]=SpectralClustering(n_clusters=8,affinity='precomputed',random_state=370,n_init=10).fit_predict(g)
            results[name]['spectral_warnings']=[str(w.message) for w in got]
    except Exception as exc:results[name]['spectral_error']=type(exc).__name__+': '+str(exc)
for other in comparisons:
    if 'builtin' in labels and other in labels:comparisons[other]['spectral_cluster_ari']=float(adjusted_rand_score(labels['builtin'],labels[other]))
summary={'posthoc':True,'input_sha256':expected,'prior_neighbors_sha256':hashlib.sha256((prior/'neighbors.csv').read_bytes()).hexdigest(),
 'prior_genes_sha256':hashlib.sha256((prior/'selected-genes.csv').read_bytes()).hexdigest(),
 'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'versions':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'scanpy':sc.__version__,'anndata':anndata.__version__,'umap':umap.__version__},
 'n_cells':128,'n_genes':1000,'paths':results,'comparisons':comparisons,'elapsed_seconds':time.monotonic()-start}
with (out/'results.json').open('x',encoding='utf8') as f:json.dump(summary,f,indent=2,allow_nan=False)
print(json.dumps(summary,indent=2))
