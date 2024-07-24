# TODO: Update this to match the project reqs.

import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='JavaScript Test Migration',
    author='Cameron Parker',
    author_email='cameron@cameronparker.ca',
    description='JavaScript Test Migration Tool',
    keywords='',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    project_urls={
        'Documentation': '',
        'Bug Reports': '',
        'Source Code': '',
        'Website': '',
    },
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
    install_requires=[
    ],
    extras_require={
        'inference': [
            'openai',     
        ],
    },
    include_package_data=True,
)