"""
Flask-MongoDB-Admin
-------------------

Flask-Mongodb-Admin is a Flask extension module. Web-based interface to your mongoDB.

"""
from setuptools import setup


setup(
    name='Flask-Mongodb-Admin',
    version='0.0.1',
    url='https://github.com/olebedev/flask-mongodb-admin',
    license = 'MIT license',
    author='Oleg Lebedev',
    author_email='mail@olebedev.ru',
    description='Add Flask support for web-based admin interface to your mongoDB using MongoAlchemy.',
    long_description=__doc__,
    packages=['flaskext', 
              'flaskext.admin'],
    namespace_packages=['flaskext'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask',
        'Flask-MongoAlchemy'
    ],
    classifiers=(
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ),
)
