# -*- encoding: utf-8 -*-
"""setup.py: Django Input Collection"""

from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = list(filter(bool, (line.strip() for line in f)))

setup(name='django-input-collection',
      version='2.2.3',
      description='Input system driveable by any interaction process, such as a request-response cycle, API, or a Python function.',
      author='Autumn Valenta',
      author_email='avalenta@pivotalenergysolutions.com',
      url='https://github.com/pivotal-energy-solutions/django-input-collection',
      download_url='https://github.com/pivotal-energy-solutions/django-input-collection/tarball/django-input-collection-0.1.0-alpha.1',
      license='Apache License (2.0)',
      classifiers=[
           'Development Status :: 2 - Pre-Alpha',
           'Environment :: Web Environment',
           'Framework :: Django',
           'Intended Audience :: Developers',
           'License :: OSI Approved :: Apache Software License',
           'Operating System :: OS Independent',
           'Programming Language :: Python',
           'Topic :: Software Development',
      ],
      packages=find_packages(exclude=['tests', 'tests.*']),
      package_data={'django_input_collection': ['static/input/*.js']},
      include_package_data=True,
      install_requires=requirements,
)
