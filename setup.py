from setuptools import setup, find_packages

setup(
    name="crawling_agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.22.0",
        "pydantic>=2.0.0",
        "requests>=2.28.0",
        "pandas>=1.5.0",
        "pyyaml>=6.0",
        "pymongo>=4.3.0"
    ],
)