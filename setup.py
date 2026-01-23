"""
D10Z Universal Nodal Architecture (NQAE)
Software-Defined Implementation Framework for D10Z-TTA Nodal Networks

Version: v18
Published: January 23, 2026
DOI: 10.5281/zenodo.18348037
Rights Holder: D10Z Institute
"""

from setuptools import setup, find_packages
import os

# Read long description from README
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="d10z-nqae",
    version="18.0.0",
    author="D10Z Institute",
    author_email="contact@d10z.institute",
    
    description="D10Z Universal Nodal Architecture - Coherence-Based Infrastructure for the 2030 Horizon",
    long_description=long_description,
    long_description_content_type="text/markdown",
    
    url="https://github.com/d10z-institute/d10z-nqae",
    download_url="https://doi.org/10.5281/zenodo.18348037",
    
    license="CC BY-NC 4.0",
    
    classifiers=[
        # Development Status
        "Development Status :: 4 - Beta",
        
        # Intended Audience
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        
        # License
        "License :: OSI Approved :: Creative Commons Attribution Non Commercial (CC BY-NC 4.0)",
        
        # Operating System
        "Operating System :: OS Independent",
        
        # Programming Language
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        
        # Topic
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Networking",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    
    keywords=[
        "d10z", "nodal", "architecture", "coherence", "compression",
        "mesh-network", "distributed-computing", "edge-computing",
        "ai-infrastructure", "smart-cities", "iot", "p2p",
        "energy-efficiency", "zero-loss", "sovereign-ai",
        "gcc", "neom", "qatar", "hail", "qai"
    ],
    
    packages=find_packages(
        where="src",
        exclude=["docs*", "tests*", "examples*", "assets*", "config*"]
    ),
    
    package_dir={"": "src"},
    
    python_requires=">=3.10",
    
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "pandas>=2.0.0",
        "torch>=2.0.0",
        "sktime>=0.20.0",
        "pyyaml>=6.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
    ],
    
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.0",
            "mypy>=1.5.0",
            "pylint>=2.17.0",
            "black>=23.9.0",
            "ipython>=8.14.0",
        ],
        "docs": [
            "sphinx>=7.2.0",
            "sphinx-rtd-theme>=1.3.0",
            "myst-parser>=2.0.0",
        ],
        "benchmark": [
            "pytest-benchmark>=4.0.0",
            "cProfileV>=1.1.0",
            "memory-profiler>=0.61.0",
        ],
        "statistical": [
            "pymc>=5.7.0",
            "arviz>=0.16.0",
        ],
    },
    
    entry_points={
        "console_scripts": [
            "d10z-analyze=d10z.utils.cli:main",
            "d10z-compress=d10z.utils.compress_cli:main",
            "d10z-validate=d10z.utils.validate_cli:main",
        ],
    },
    
    include_package_data=True,
    
    package_data={
        "d10z": [
            "config/*.yaml",
            "assets/*",
        ],
    },
    
    project_urls={
        "Bug Reports": "https://github.com/d10z-institute/d10z-nqae/issues",
        "Source": "https://github.com/d10z-institute/d10z-nqae",
        "Documentation": "https://docs.d10z.institute",
        "Zenodo": "https://doi.org/10.5281/zenodo.18348037",
        "Prior Art": "https://zenodo.org/record/18348037",
    },
    
    zip_safe=False,
    
    # Metadata for PyPI
    keywords=[
        "d10z", "nodal network", "mesh network", "coherence",
        "compression", "edge computing", "distributed systems"
    ],
)
