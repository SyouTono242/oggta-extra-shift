import os
from distutils.core import setup

lib_folder = os.path.dirname(os.path.realpath(__file__))

# Requirements
requirement_path = f"{lib_folder}/requirements.txt"
install_requires = []
if os.path.isfile(requirement_path):
    with open(requirement_path) as f:
        install_requires = f.read().splitlines()

# Setup
setup(
    name='OGGTA-Extra-Shift',
    version='1.0',
    packages=['OGGTA-Extra-Shift'],
    license='MIT License',
    long_description=open('README.md').read(),
    install_requires=install_requires,
)