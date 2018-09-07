import pytest

from cwltool.secrets import SecretStore

from .util import get_data

@pytest.fixture
def secrets():
    sec_store = SecretStore()
    job = {'foo': 'bar',
           'baz': 'quux'}

    sec_store.store(['foo'], job)
    return sec_store, job

def test_obscuring(secrets):
    storage, obscured = secrets
    assert obscured['foo'] != 'bar'
    assert obscured['baz'] == 'quux'
    assert storage.retrieve(obscured)['foo'] == 'bar'

obscured_factories_expected = [
    ((lambda x: 'hello %s' % x), 'hello bar'),
    ((lambda x: ['echo', 'hello %s' % x]), ['echo', 'hello bar']),
    ((lambda x: {'foo': x}), {'foo': 'bar'}),
]

@pytest.mark.parametrize('factory,expected', obscured_factories_expected)
def test_secrets(factory, expected, secrets):
    storage, obscured = secrets
    pattern = factory(obscured['foo'])
    assert pattern != expected

    assert storage.has_secret(pattern)
    assert storage.retrieve(pattern) == expected

    assert obscured['foo'] != 'bar'
    assert obscured['baz'] == 'quux'
