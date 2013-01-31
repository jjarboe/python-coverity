from setuptools import setup

setup(
    name='coverity',
    version='0.1.0',
    author='Jon Jarboe',
    author_email='jjarboe@coverity.com',
    packages=['coverity','coverity.ws', 'coverity.email', 'coverity.templates'],
    scripts=['bin/doemail.py'],
    url='http://pypi.python.org/pypi/Coverity/',
    license='LICENSE.txt',
    description='Module that simplifies access to Coverity services.',
    long_description=open('README.txt').read(),
    requires=[
        "suds (>=0.4)",
    ],
)
