import yaml

import e3.electrolyt.hosts as hosts


def test_host_db():
    db = hosts.HostDB()
    db.add_host(hostname='computer1',
                platform='x86_64-linux',
                version='rhes5',
                data_center='dc832')

    assert db.hostnames == ['computer1']
    assert db.get('computer1').data_center == 'dc832', \
        db.get('computer1').__dict__
    assert db['computer1'].platform == 'x86_64-linux'


def test_host_db_yaml():
    with open('db.yaml', 'wb') as f:
        yaml.dump(data={'computer2': {'build_platform': 'x86-windows',
                                      'build_os_version': '2008R2',
                                      'data_center': 'dc993'},
                        'computer3': {'build_platform': 'x86_64-darwin',
                                      'build_os_version': '16.3',
                                      'data_center': 'dcmac'}},
                  stream=f)

    db = hosts.HostDB(filename='db.yaml')
    assert set(db.hostnames) == {'computer2', 'computer3'}
    assert db['computer3'].platform == 'x86_64-darwin'
