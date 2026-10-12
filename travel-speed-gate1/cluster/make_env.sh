#!/bin/bash
# Build the cluster Python env /engrfs/project/jacobsn/zhou.n/envs/t1
# (Python 3.12, packages in ../requirements-pipeline.txt).
#
# The cluster could not reach files.pythonhosted.org (Oct 2026), so the
# packages are installed OFFLINE from Linux wheels downloaded on a laptop
# (on the cluster: wheels_linux/ = the first set, wheels/ = scikit-learn,
# rasterio, laspy, lazrs and their dependencies, added 11-12 Oct):
#   pip download -r requirements-pipeline.txt -d wheels_linux \
#       --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
#       --python-version 3.12 --only-binary=:all:
#   tar czf - wheels_linux | ssh zhou.n@shell3.engr.wustl.edu \
#       'tar xzf - -C /engrfs/project/jacobsn/zhou.n'
# (one stream: many small files over scp/rsync are slow on BeeGFS).
# Then on the cluster:  bash make_env.sh
set -e
BASE=/engrfs/project/jacobsn/zhou.n
ENV=$BASE/envs/t1
export MAMBA_ROOT_PREFIX=$BASE/micromamba
export PIP_NO_CACHE_DIR=1
/project/compute/slurm/bin/micromamba create -y -p $ENV -c conda-forge \
    python=3.12 pip
$ENV/bin/pip install --no-index --find-links $BASE/wheels_linux \
    --find-links $BASE/wheels -r $BASE/travel-speed/requirements-pipeline.txt
$ENV/bin/python -c "import numpy, pandas, pyarrow, scipy, matplotlib, \
requests, tifffile, pyproj, rtree, leuvenmapmatching, sklearn, rasterio, \
laspy; print('ENV OK', pandas.__version__)"
