"""Setup configuration for Blustream package."""

from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="blustream",
    version="0.1.0",
    description="Python library and CLI for controlling Blustream audio devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/caidurbin/blustream",
    packages=find_packages(
        exclude=[
            "custom_components", "custom_components.*",
            "tests", "tests.*",
            "spec", "spec.*",
            "tools", "tools.*",
        ],
    ),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "telnetlib3>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "blustream=blustream.cli.main:main",
        ],
    },
)

