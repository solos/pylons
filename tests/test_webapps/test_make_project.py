"""Tests against full Pylons projects created from scratch"""
import os
import sys
import time
from shutil import rmtree

import pkg_resources
import nose
import nose.config
import pylons
from nose import SkipTest
from paste.fixture import *

is_jython = sys.platform.startswith('java')

TEST_OUTPUT_DIRNAME = 'output'

for spec in ['PasteScript', 'Paste', 'PasteDeploy', 'pylons']:
    pkg_resources.require(spec)

template_path = os.path.join(
    os.path.dirname(__file__), 'filestotest').replace('\\','/')

test_environ = os.environ.copy()
test_environ['PASTE_TESTING'] = 'true'

testenv = TestFileEnvironment(
    os.path.join(os.path.dirname(__file__), TEST_OUTPUT_DIRNAME).replace('\\','/'),
    template_path=template_path,
    environ=test_environ)

projenv = None

def _get_script_name(script):
    if sys.platform == 'win32':
        script += '.exe'
    return script

def svn_repos_setup():
    res = testenv.run(_get_script_name('svnadmin'), 'create', 'REPOS',
                      printresult=False)
    path = testenv.base_path.replace('\\','/').replace(' ','%20')
    base = 'file://'
    if ':' in path:
        base = 'file:///'
    testenv.svn_url = base + path + '/REPOS'
    assert 'REPOS' in res.files_created
    testenv.ignore_paths.append('REPOS')

def paster_create(template_engine='mako', overwrite=False):
    global projenv
    paster_args = ['create', '--verbose', '--no-interactive']
    if overwrite:
        paster_args.append('-f')
    paster_args.extend(['--template=pylons',
                        'ProjectName',
                        'version=0.1',
                        'sqlalchemy=False',
                        'zip_safe=False',
                        'template_engine=%s' % template_engine])
    res = testenv.run(_get_script_name('paster'), *paster_args)
    expect_fn = ['projectname', 'development.ini', 'setup.cfg', 'README.txt',
                 'setup.py']
    for fn in expect_fn:
        fn = os.path.join('ProjectName', fn)
        if not overwrite:
            assert fn in res.files_created.keys()
        assert fn in res.stdout

    if not overwrite:
        setup = res.files_created[os.path.join('ProjectName','setup.py')]
        setup.mustcontain('0.1')
        setup.mustcontain('projectname.config.middleware:make_app')
        setup.mustcontain('main = pylons.util:PylonsInstaller')
        setup.mustcontain("include_package_data=True")
        assert '0.1' in setup
    testenv.run(_get_script_name(sys.executable)+' setup.py egg_info',
                cwd=os.path.join(testenv.cwd, 'ProjectName').replace('\\','/'),
                expect_stderr=True)
    #testenv.run(_get_script_name('svn'), 'commit', '-m', 'Created project', 'ProjectName')
    # A new environment with a new
    projenv = TestFileEnvironment(
        os.path.join(testenv.base_path, 'ProjectName').replace('\\','/'),
        start_clear=False,
        template_path=template_path,
        environ=test_environ)
    projenv.environ['PYTHONPATH'] = (
        projenv.environ.get('PYTHONPATH', '') + ':'
        + projenv.base_path)

def make_controller():
    res = projenv.run(_get_script_name('paster')+' controller sample')
    assert os.path.join('projectname','controllers','sample.py') in res.files_created
    assert os.path.join('projectname','tests','functional','test_sample.py') in res.files_created
    #res = projenv.run(_get_script_name('svn')+' status')
    # Make sure all files are added to the repository:
    assert '?' not in res.stdout

def make_restcontroller():
    res = projenv.run(_get_script_name('paster')+' restcontroller restsample restsamples')
    assert os.path.join('projectname','controllers','restsamples.py') in res.files_created
    assert os.path.join('projectname','tests','functional','test_restsamples.py') in res.files_created
    #res = projenv.run(_get_script_name('svn')+' status')
    # Make sure all files are added to the repository:
    assert '?' not in res.stdout

def _do_proj_test(copydict, emptyfiles=None):
    """Given a dict of files, where the key is a filename in filestotest, the value is
    the destination in the new projects dir. emptyfiles is a list of files that should
    be created and empty."""
    if is_jython:
        # Hack for Jython .py/bytecode mtime handling:
        # http://bugs.jython.org/issue1024 (the issue actually describes
        # this test)
        time.sleep(1)
    
    if pylons.test.pylonsapp:
        pylons.test.pylonsapp = None
    
    if not emptyfiles:
        emptyfiles = []
    for original, newfile in copydict.iteritems():
        projenv.writefile(newfile, frompath=original)
    for fi in emptyfiles:
        projenv.writefile(fi)
    
    # here_dir = os.getcwd()
    # test_dir = os.path.join(testenv.cwd, 'ProjectName').replace('\\','/')
    # os.chdir(test_dir)
    # sys.path.append(test_dir)
    # nose.run(argv=['nosetests', '-d', test_dir])
    # 
    # sys.path.pop(-1)
    # os.chdir(here_dir)
    
    res = projenv.run(_get_script_name('nosetests')+' -d --with-coverage --cover-package=pylons',
                      expect_stderr=True,
                      cwd=os.path.join(testenv.cwd, 'ProjectName').replace('\\','/'))

def do_nosetests():
    _do_proj_test({'development.ini':'development.ini'})

def do_knowntest():
    copydict = {
        'helpers_sample.py':'projectname/lib/helpers.py',
        'controller_sample.py':'projectname/controllers/sample.py',
        'app_globals.py':'projectname/lib/app_globals.py',
        'functional_sample_controller_sample1.py':'projectname/tests/functional/test_sample.py',
    }
    _do_proj_test(copydict)

def do_i18ntest():
    copydict = {
        'functional_sample_controller_i18n.py':'projectname/tests/functional/test_i18n.py',
        'messages.ja.po':'projectname/i18n/ja/LC_MESSAGES/projectname.po',
        'messages.ja.mo':'projectname/i18n/ja/LC_MESSAGES/projectname.mo',
    }
    _do_proj_test(copydict)

def do_genshi():
    paster_create(template_engine='genshi', overwrite=True)
    reset = {
        'helpers_sample.py':'projectname/lib/helpers.py',
        'app_globals.py':'projectname/lib/app_globals.py',
        'rest_routing.py':'projectname/config/routing.py',
        'development.ini':'development.ini',
        }
    copydict = {
        'testgenshi.html':'projectname/templates/testgenshi.html',
        'middleware_def_engine.py':'projectname/config/middleware.py',
        'functional_sample_controller_sample2.py':'projectname/tests/functional/test_sample2.py'
    }
    copydict.update(reset)
    empty = ['projectname/templates/__init__.py', 'projectname/tests/functional/test_cache.py']
    _do_proj_test(copydict, empty)

def do_two_engines():
    copydict = {
        'middleware_two_engines.py':'projectname/config/middleware.py',
        'test_mako.html':'projectname/templates/test_mako.html',
        'functional_sample_controller_sample3.py':'projectname/tests/functional/test_sample2.py',
    }
    _do_proj_test(copydict)

def do_crazy_decorators():
    _do_proj_test({'functional_sample_controller_sample4.py':'projectname/tests/functional/test_sample3.py'})

def do_jinja2():
    paster_create(template_engine='jinja2', overwrite=True)
    reset = {
        'helpers_sample.py':'projectname/lib/helpers.py',
        'app_globals.py':'projectname/lib/app_globals.py',
        'rest_routing.py':'projectname/config/routing.py',
        'development.ini':'development.ini',
        }
    copydict = {
        'controller_sample.py':'projectname/controllers/sample.py',
        'testjinja2.html':'projectname/templates/testjinja2.html',
        'functional_sample_controller_jinja2.py':'projectname/tests/functional/test_jinja2.py',
    }
    copydict.update(reset)
    empty = [
         'projectname/templates/__init__.py',
         'projectname/tests/functional/test_sample.py',
         'projectname/tests/functional/test_sample2.py',
         'projectname/tests/functional/test_sample3.py',
         'projectname/tests/functional/test_cache.py'
     ]
    _do_proj_test(copydict, empty)

def do_cache_decorator():
    copydict = {
        'middleware_mako.py':'projectname/config/middleware.py',
        'app_globals.py':'projectname/lib/app_globals.py',
        'cache_controller.py':'projectname/controllers/cache.py',
        'functional_controller_cache_decorator.py':'projectname/tests/functional/test_cache.py',
    }
    empty = [
        'projectname/tests/functional/test_mako.py',
        'projectname/tests/functional/test_jinja2.py',
        'projectname/tests/functional/test_sample.py',
        'projectname/tests/functional/test_sample2.py',
        'projectname/tests/functional/test_sample3.py'
     ]
    _do_proj_test(copydict, empty)

def do_xmlrpc():
    copydict = {
        'middleware_mako.py':'projectname/config/middleware.py',
        'base_with_xmlrpc.py':'projectname/lib/base.py',
        'controller_xmlrpc.py':'projectname/controllers/xmlrpc.py',
        'functional_controller_xmlrpc.py':'projectname/tests/functional/test_xmlrpc.py'
    }
    empty = [
        'projectname/tests/functional/test_cache.py',
        'projectname/tests/functional/test_jinja2.py',
    ]
    _do_proj_test(copydict, empty)

def do_legacy_app():
    legacyenv = TestFileEnvironment(
        os.path.join(testenv.base_path, 'legacyapp').replace('\\','/'),
        start_clear=False,
        template_path=template_path,
        environ=test_environ)
    res = legacyenv.run(_get_script_name('nosetests')+' legacyapp/tests',
                      expect_stderr=True,
                      cwd=os.path.join(testenv.cwd, 'legacyapp').replace('\\','/'))

def make_tag():
    global tagenv
    #res = projenv.run(_get_script_name('svn')+' commit -m "updates"')
    # Space at the end needed so run() doesn't add \n causing svntag to complain
    #res = projenv.run(_get_script_name(sys.executable)+' setup.py svntag --version=0.5 ')
    # XXX Still fails => setuptools problem on win32?
    assert 'Tagging 0.5 version' in res.stdout
    assert 'Auto-update of version strings' in res.stdout
    res = testenv.run(_get_script_name('svn')+' co %s/ProjectName/tags/0.5 Proj-05 '
                      % testenv.svn_url)
    setup = res.files_created['Proj-05/setup.py']
    setup.mustcontain('0.5')
    assert 'Proj-05/setup.cfg' not in res.files_created
    tagenv = TestFileEnvironment(
        os.path.join(testenv.base_path, 'Proj-05').replace('\\','/'),
        start_clear=False,
        template_path=template_path)


# Unfortunately, these are ordered, so be careful
def test_project_paster_create():
    paster_create()

def test_project_make_controller():
    make_controller()

def test_project_do_nosetests():
    do_nosetests()

def test_project_do_knowntest():
    do_knowntest()

def test_project_do_i18ntest():
    do_i18ntest()

def test_project_make_restcontroller():
    make_restcontroller()

def test_project_do_rest_nosetests():
    copydict = {
        'rest_routing.py':'projectname/config/routing.py',
        'development.ini':'development.ini',
    }
    _do_proj_test(copydict)

# Tests with templating plugin dependencies
def test_project_do_crazy_decorators():
    do_crazy_decorators()

def test_project_do_cache_decorator():
    do_cache_decorator()

def test_project_do_genshi_default():
    if is_jython:
        raise SkipTest('Jython does not currently support Genshi')
    do_genshi()

def test_project_do_two_engines():
    do_two_engines()

def test_project_do_jinja2():
    if is_jython:
        raise SkipTest('Jython does not currently support Jinja2')
    do_jinja2()

def test_project_do_xmlrpc():
    do_xmlrpc()

#def test_project_do_legacy_app():
#    do_legacy_app()

#def test_project_make_tag():
#    make_tag()

def teardown():
    dir_to_clean = os.path.join(os.path.dirname(__file__), TEST_OUTPUT_DIRNAME)
    rmtree(dir_to_clean)
