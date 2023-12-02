# Structured Light Scanning Simulation.

For all information regarding the dataset and the data generation framework, see our website https://geometryprocessing.github.io/scanner-sim/.

## Installation instructions (gromovnik1337 fork)
Installation had been done & validated on Ubuntu 22.04. Notes were made on the differences between 22.04 and 20.04.

Clone the fork & initialize submodules: 
```bash
git clone https://github.com/gromovnik1337/scanner-sim.git
git submodule update --init
```

Install basic dependencies:
```bash
sudo apt-get update
sudo apt-get install git python3-pip cmake
sudo apt-get install build-essential scons mercurial libpng-dev libjpeg-dev libilmbase-dev libxerces-c-dev libboost-all-dev libopenexr-dev libglewmx-dev libxxf86vm-dev libpcrecpp0v5
```

Install extra dependencies:
```bash
# Ubuntu 20.04:
sudo add-apt-repository ppa:rock-core/qt4
# Ubuntu 22.04:
sudo add-apt-repository ppa:ubuntuhandbook1/ppa

sudo apt install qt4-dev-tools
sudo apt install libeigen3-dev
sudo apt install libqt4-dev
```

Install `mitsuba`:
```bash
cd mitsuba
cp build/config-linux-gcc.py config.py

scons -j 1 ; echo -e '\a'
```
Possible errors with `mitsuba` installation (some corrected in the fork):
```bash
# lfftw3_threads:
sudo apt install --reinstall libfftw3-dev
```

```bash
# /usr/bin/ld: build/release/libcore/chisquare.os: relocation R_X86_64_PC32 against undefined hidden symbol `_ZTCN5boost10wrapexceptINS_4math14rounding_errorEEE0_NS_16exception_detail10clone_implINS4_19error_info_injectorIS2_EEEE' can not be used when making a shared object
# /usr/bin/ld: final link failed: bad value
# In mitsuba/build/SConscript.configure change:
env.Append(CPPFLAGS=['-std=gnu++11'])
```

```bash
# Issues with "_1":
# in mitsuba/src/volume/volcache.cpp:
# Add: 
# include <functional>
# Change lines 181 and 182 to:
std::bind(&CachingDataSource::renderBlock, this, std::placeholders::_1),
std::bind(&CachingDataSource::destroyBlock, this, std::placeholders::_1));
```

Add the `mitsuba` to the current path:
```bash
echo "# scanner-sim" >> ~/.bashrc
echo "source $PWD/setpath.sh" >> ~/.bashrc
source ~/.bashrc
# N.B. Manually check .bashrc to make sure all the paths are okay & the syntax is ok (backslash for space etc.).
```

The project requires Python version <= 3.9 as some of it's dependencies are tied to the mentioned max version. Follow the next steps if the system's default `python3` is > 3.9 (which is the case for Ubuntu 22.04 which uses Python 3.10).
```bash
sudo apt-get update && sudo apt-get upgrade
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.9
sudo apt-get install python3.9-distutils # Requirement for pip.
sudo apt-get install python3.9-dev # Headers & static libs for dev use.
sudo apt install python3.9-tk
```
Create a `venv` using Python 3.9 in the main dir of the project & enable the usage of external packages:
```bash
sudo apt install python3-virtualenv
cd ..
virtualenv venv -p python3.9
nano venv/pyvenv.cfg
# Edit: 
include-system-site-packages = true
```
Install project's Python requirements:
```bash
source venv/bin/activate
cat requirements.txt | xargs -t -i sh -c 'pip3 install -U {} || true'
```

A simple setup.py was created to install project modules with: `pip install -e .`

Possible runtime errors (after installation & when trying to run some of the validation experiments):
```bash
# OpenEXR error:
pip uninstall openexr
pip install git+https://github.com/jamesbowman/openexrpython.git
```

```bash
# mathplotlib:
sudo apt remove python3-matplotlib
pip uninstall matplotlib
pip install matplotlib
```

```bash
# ModuleNotFoundError: No module named 'kiwisolver':
sudo rm -r /usr/lib/python3/dist-packages/kiwisolver-1.3.2.egg-info/ # Possibly other version of kiwisolver.
pip install kiwisolver
```

```bash
# ModuleNotFoundError: No module named '_cffi_backend'
sudo rm -r /usr/lib/python3/dist-packages/cffi-1.15.0.egg-info/
pip install cffi
```

If errors were present & sorted, do pip install -e . again (for good measure).
If no other dependancies are required, with this step, one can proceed to reproduce validation experiments in `simulator/validation`.

### Lucid Arena Dependancy
Download Arena SDK (Python) from: https://thinklucid.com/downloads-hub/
First, add SDK Linux library into the dynamic library linker. To do this, unpack the .tar file and follow the instructions in the README. Basically, cd into the folder of the library and run the .conf shell script inside of it with `sudo sh Arena_SDK_Linux_x64.conf`.  This script will add the Arena SDK paths to the `/etc/ld.so.conf.d`. Be mindful to the spaces in the path! If there are spaces present, `ldconfig` (at the end of the shell script) will fail. Do `ldconfig -v` to get more info.

After that, Python API is to be downloaded (from the same link) and installed. Extract the .zip and install the wheels (**inside the `venv`**) as: `pip install arena_api-2.3.3-py3-none-any.whl`. Finally, manually point the API installed in the venv to the SDK binaries by editing: `/scanner-sim/venv/lib/python3.9/site-packages/arena_api/arena_api_config.py` as so:
```Python
ARENAC_CUSTOM_PATHS = {
    'python32_win': '',
    'python64_win': '',
    'python32_lin': '',
    'python64_lin': 'absolute/path/to/ArenaSDK_Linux_x64/lib64/libarenac.so'
}

SAVEC_CUSTOM_PATHS = {
    'python32_win': '',
    'python64_win': '',
    'python32_lin': '',
    'python64_lin': 'absolute/path/to/ArenaSDK_Linux_x64/lib64/libsavec.so'
}
```

### Sources
- https://ubuntuhandbook.org/index.php/2020/07/install-qt4-ubuntu-20-04/#google_vignette
- https://stackoverflow.com/questions/62737525/how-to-fix-error-1-was-not-declared-in-this-scope
- https://github.com/jamesbowman/openexrpython/issues/28
- https://github.com/matplotlib/matplotlib/issues/26827 
- https://man7.org/linux/man-pages/man8/ldconfig.8.html