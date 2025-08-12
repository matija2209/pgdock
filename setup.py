from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pgdock",
    version="1.0.0",
    author="pgdock",
    description="A CLI tool for managing PostgreSQL Docker instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.12.0",
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "rich>=13.0.0",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pgdock=pgdock.cli:app",
        ],
    },
)