from setuptools import setup, find_packages

setup(
    name="worker_agent",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "huggingface_hub",
        "stdlib_list"
    ],
    entry_points={
        "console_scripts": [
            "worker-agent=core.main:main",
        ],
    },
    description="A package for generating Python code using AI.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/gogoboyia/worker-agent",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
