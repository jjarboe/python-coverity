# Work even if the user doesn't yet have setuptools
import distribute_setup
distribute_setup.use_setuptools()
from setuptools import setup

setup(
    name='coverity',
    version='0.1.0',
    author='Jon Jarboe',
    author_email='jjarboe@coverity.com',
    packages=['coverity','coverity.ws', 'coverity.email', 'coverity.templates', 'coverity.roi'],
    scripts=['bin/cov_doemail.py'],
    url='http://pypi.python.org/pypi/Coverity/',
    license='LICENSE.txt',
    description='Module that simplifies access to Coverity services.',
    long_description=open('README.txt').read(),
    install_requires=[
        "suds >= 0.4",
    ],
)
