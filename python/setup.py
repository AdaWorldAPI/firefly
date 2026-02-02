from setuptools import setup, find_packages

setup(
    name="firefly",
    version="0.1.0",
    description="Bioluminescent Code Execution - Compile any language to executable graph",
    author="Ada",
    author_email="ada@adaworld.ai",
    url="https://github.com/AdaWorldAPI/firefly",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "click>=8.0.0",
    ],
    extras_require={
        "storage": [
            "lancedb>=0.4.0",
            "duckdb>=0.9.0",
            "kuzu>=0.1.0",
        ],
        "server": [
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
        ],
        "all": [
            "lancedb>=0.4.0",
            "duckdb>=0.9.0",
            "kuzu>=0.1.0",
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "httpx>=0.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "firefly=cli:cli",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
