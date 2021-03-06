# -*- encoding: utf-8 -*-
"""setup.py: Django Input Collection"""

from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = list(filter(bool, (line.strip() for line in f)))

setup(name='django-input-collection',
      version='2.2.4',
      description='Input system driveable by any interaction process, such as a '
                  'request-response cycle, API, or a Python function.',
      author='Autumn Valenta',
      author_email='avalenta@pivotalenergysolutions.com',
      url='https://github.com/pivotal-energy-solutions/django-input-collection',
      license='Apache License (2.0)',
      classifiers=['Development Status :: 5 - Production/Stable',
                   'Environment :: Web Environment',
                   'Framework :: Django',
                   'Framework :: Django :: 2.2',
                   'Framework :: Django :: 3.0',
                   'Framework :: Django :: 3.1',
                   'Framework :: Django :: 3.2',
                   'Intended Audience :: Developers',
                   'License :: Other/Proprietary License (Proprietary)',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.8',
                   'Programming Language :: Python :: 3.9',
                   'Programming Language :: Python :: 3.10',
                   'Topic :: Utilities'
                   ],
      python_requires='>=3.8.*',
      packages=find_packages(exclude=['tests', 'tests.*']),
      package_data={'django_input_collection': ['static/input/*.js']},
      include_package_data=True,
      install_requires=requirements,
      )
