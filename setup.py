"""Setup configuration for Bluestream package."""

from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bluestream",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Python library and CLI for controlling Bluestream audio devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/caidurbin/bluestream",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "bluestream=bluestream.cli.main:main",
        ],
    },
)

