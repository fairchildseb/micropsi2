#!/usr/local/bin/python
# -*- coding: utf-8 -*-

"""

"""
import os
import mock

__author__ = 'joscha'
__date__ = '29.10.12'


def prepare(runtime, test_nodenet):
    net = runtime.nodenets[test_nodenet]
    netapi = net.netapi
    source = netapi.create_node("Register", None, "source")
    register = netapi.create_node("Register", None, "reg")
    netapi.link(source, 'gen', source, 'gen')
    netapi.link(source, 'gen', register, 'gen')
    return net, netapi, source, register


def test_new_nodenet(runtime, test_nodenet, resourcepath, engine):
    success, nodenet_uid = runtime.new_nodenet("Test_Nodenet", engine=engine, worldadapter="Default", owner="tester")
    assert success
    assert nodenet_uid != test_nodenet
    assert runtime.get_available_nodenets("tester")[nodenet_uid].name == "Test_Nodenet"
    n_path = os.path.join(resourcepath, runtime.NODENET_DIRECTORY, nodenet_uid + ".json")
    assert os.path.exists(n_path)

    # get_available_nodenets
    nodenets = runtime.get_available_nodenets()
    mynets = runtime.get_available_nodenets("tester")
    assert test_nodenet in nodenets
    assert nodenet_uid in nodenets
    assert nodenet_uid in mynets
    assert test_nodenet not in mynets

    # delete_nodenet
    runtime.delete_nodenet(nodenet_uid)
    assert nodenet_uid not in runtime.get_available_nodenets()
    assert not os.path.exists(n_path)


# def test_nodenet_data_gate_parameters(runtime, fixed_nodenet):
#     from micropsi_core.nodenet.node import Nodetype
#     data = runtime.nodenets[fixed_nodenet].get_data()
#     assert data['nodes']['n0005']['gate_parameters'] == {}
#     runtime.set_gate_parameters(fixed_nodenet, 'n0005', 'gen', {'threshold': 1})
#     data = runtime.nodenets[fixed_nodenet].get_data()
#     assert data['nodes']['n0005']['gate_parameters'] == {'gen': {'threshold': 1}}
#     defaults = Nodetype.GATE_DEFAULTS.copy()
#     defaults.update({'threshold': 1})
#     data = runtime.nodenets[fixed_nodenet].get_node('n0005').get_data()['gate_parameters']
#     assert data == {'gen': {'threshold': 1}}


def test_user_prompt(runtime, test_nodenet, resourcepath):
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    nodenet = runtime.nodenets[test_nodenet]
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "gatetypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "parameters": ["testparam"],
            "parameter_defaults": {
                "testparam": 13
              }
            }}""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")

    runtime.reload_native_modules()
    res, node_uid = runtime.add_node(test_nodenet, "Testnode", [10, 10], name="Test")
    nativemodule = nodenet.get_node(node_uid)

    options = [{'key': 'foo_parameter', 'label': 'Please give value for "foo"', 'values': [23, 42]}]
    nodenet.netapi.ask_user_for_parameter(
        nativemodule,
        "foobar",
        options
    )
    result, data = runtime.get_calculation_state(test_nodenet, nodenet={})
    assert 'user_prompt' in data
    assert data['user_prompt']['msg'] == 'foobar'
    assert data['user_prompt']['node']['uid'] == node_uid
    assert data['user_prompt']['options'] == options
    # response
    runtime.user_prompt_response(test_nodenet, node_uid, {'foo_parameter': 42}, True)
    assert nodenet.get_node(node_uid).get_parameter('foo_parameter') == 42
    assert nodenet.is_active
    from micropsi_core.nodenet import nodefunctions
    tmp = nodefunctions.concept
    nodefunc = mock.Mock()
    nodefunctions.concept = nodefunc
    nodenet.step()
    foo = nodenet.get_node(node_uid).clone_parameters()
    foo.update({'foo_parameter': 42})
    assert nodefunc.called_with(nodenet.netapi, nodenet.get_node(node_uid), foo)
    nodenet.get_node(node_uid).clear_parameter('foo_parameter')
    assert nodenet.get_node(node_uid).get_parameter('foo_parameter') is None
    nodefunctions.concept = tmp


def test_user_notification(runtime, test_nodenet, node):
    api = runtime.nodenets[test_nodenet].netapi
    node_obj = api.get_node(node)
    api.notify_user(node_obj, "Hello there")
    result, data = runtime.get_calculation_state(test_nodenet, nodenet={'nodespaces': [None]})
    assert 'user_prompt' in data
    assert data['user_prompt']['node']['uid'] == node
    assert data['user_prompt']['msg'] == "Hello there"


def test_nodespace_removal(runtime, test_nodenet):
    res, uid = runtime.add_nodespace(test_nodenet, nodespace=None, name="testspace")
    res, n1_uid = runtime.add_node(test_nodenet, 'Register', [100, 100], nodespace=uid, name="sub1")
    res, n2_uid = runtime.add_node(test_nodenet, 'Register', [100, 200], nodespace=uid, name="sub2")
    runtime.add_link(test_nodenet, n1_uid, 'gen', n2_uid, 'gen', weight=1)
    res, sub_uid = runtime.add_nodespace(test_nodenet, nodespace=uid, name="subsubspace")
    runtime.delete_nodespace(test_nodenet, uid)
    # assert that the nodespace is gone
    assert not runtime.nodenets[test_nodenet].is_nodespace(uid)
    assert uid not in runtime.nodenets[test_nodenet].get_data()['nodespaces']
    # assert that the nodes it contained are gone
    assert not runtime.nodenets[test_nodenet].is_node(n1_uid)
    assert n1_uid not in runtime.nodenets[test_nodenet].get_data()['nodes']
    assert not runtime.nodenets[test_nodenet].is_node(n2_uid)
    assert n2_uid not in runtime.nodenets[test_nodenet].get_data()['nodes']
    # assert that sub-nodespaces are gone as well
    assert not runtime.nodenets[test_nodenet].is_nodespace(sub_uid)
    assert sub_uid not in runtime.nodenets[test_nodenet].get_data()['nodespaces']


def test_clone_nodes_nolinks(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    nodenet = runtime.get_nodenet(test_nodenet)
    success, result = runtime.clone_nodes(test_nodenet, [source.uid, register.uid], 'none', offset=[10, 20, 2])
    assert success
    for n in result.values():
        if n['name'] == source.name:
            source_copy = n
        elif n['name'] == register.name:
            register_copy = n
    assert nodenet.is_node(source_copy['uid'])
    assert source_copy['uid'] != source.uid
    assert source_copy['type'] == nodenet.get_node(source.uid).type
    assert source_copy['parameters'] == nodenet.get_node(source.uid).clone_parameters()
    assert source_copy['position'][0] == nodenet.get_node(source.uid).position[0] + 10
    assert source_copy['position'][1] == nodenet.get_node(source.uid).position[1] + 20
    assert source_copy['position'][2] == nodenet.get_node(source.uid).position[2] + 2
    assert nodenet.is_node(register_copy['uid'])
    assert register_copy['name'] == nodenet.get_node(register.uid).name
    assert register_copy['uid'] != register.uid
    assert len(result.keys()) == 2
    assert source_copy['links'] == {}
    assert register_copy['links'] == {}


def test_clone_nodes_all_links(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    nodenet = runtime.get_nodenet(test_nodenet)
    thirdnode = netapi.create_node('Register', None, 'third')
    netapi.link(thirdnode, 'gen', register, 'gen')
    success, result = runtime.clone_nodes(test_nodenet, [source.uid, register.uid], 'all')
    assert success
    # expect 3 instead of two results, because thirdnode should be delivered
    # as a followupdnode to source_copy to render incoming links
    assert len(result.keys()) == 3
    for n in result.values():
        if n['name'] == source.name:
            source_copy = n
        elif n['name'] == register.name:
            register_copy = n

    # assert the links between the copied nodes exist:
    assert len(source_copy['links']['gen']) == 2
    assert set([l['target_node_uid'] for l in source_copy['links']['gen']]) == {source_copy['uid'], register_copy['uid']}

    # assert the link between thirdnode and register-copy exists
    third = nodenet.get_node(thirdnode.uid).get_data()
    assert len(third['links']['gen']) == 2
    assert set([l['target_node_uid'] for l in third['links']['gen']]) == {register.uid, register_copy['uid']}


def test_clone_nodes_internal_links(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    thirdnode = netapi.create_node('Register', None, 'third')
    netapi.link(thirdnode, 'gen', register, 'gen')
    success, result = runtime.clone_nodes(test_nodenet, [source.uid, register.uid], 'internal')
    assert success
    assert len(result.keys()) == 2
    for n in result.values():
        if n['name'] == source.name:
            source_copy = n
        elif n['name'] == register.name:
            register_copy = n

    # assert the links between the copied nodes exist:
    assert len(source_copy['links']['gen']) == 2
    assert set([l['target_node_uid'] for l in source_copy['links']['gen']]) == {source_copy['uid'], register_copy['uid']}

    # assert the link between thirdnode and register-copy does not exist
    third = net.get_node(thirdnode.uid).get_data()
    assert len(third['links']['gen']) == 1


def test_clone_nodes_to_new_nodespace(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    thirdnode = netapi.create_node('Register', None, 'third')
    netapi.link(thirdnode, 'gen', register, 'gen')
    success, result = runtime.clone_nodes(test_nodenet, [source.uid, register.uid], 'internal')

    res, testspace_uid = runtime.add_nodespace(test_nodenet, nodespace=None, name="testspace")

    success, result = runtime.clone_nodes(test_nodenet, [source.uid, register.uid], 'internal', nodespace=testspace_uid)
    assert success
    assert len(result.keys()) == 2
    for n in result.values():
        if n['name'] == source.name:
            source_copy = n
        elif n['name'] == register.name:
            register_copy = n

    source_copy = net.get_node(source_copy['uid'])
    register_copy = net.get_node(register_copy['uid'])

    assert source_copy.parent_nodespace == testspace_uid
    assert register_copy.parent_nodespace == testspace_uid


# def test_clone_nodes_copies_gate_params(fixed_nodenet):
#     nodenet = micropsi.get_nodenet(fixed_nodenet)
#     micropsi.set_gate_parameters(fixed_nodenet, 'n0001', 'gen', {'maximum': 0.1})
#     success, result = micropsi.clone_nodes(fixed_nodenet, ['n0001'], 'internal')
#     assert success
#     copy = nodenet.get_node(list(result.keys())[0])
#     assert round(copy.get_gate_parameters()['gen']['maximum'], 2) == 0.1


def test_modulators(runtime, test_nodenet, engine):
    nodenet = runtime.get_nodenet(test_nodenet)
    # assert modulators are instantiated from the beginning
    assert nodenet._modulators != {}
    assert nodenet.get_modulator('emo_activation') is not None

    # set a modulator
    nodenet.set_modulator("test_modulator", -1)
    assert nodenet.netapi.get_modulator("test_modulator") == -1

    # assert change_modulator sets diff.
    nodenet.netapi.change_modulator("test_modulator", 0.42)
    assert round(nodenet.netapi.get_modulator("test_modulator"), 4) == -0.58

    # no modulators should be set if we disable the emotional_parameter module
    res, uid = runtime.new_nodenet('foobar', engine, use_modulators=False)
    new_nodenet = runtime.get_nodenet(uid)
    assert new_nodenet._modulators == {}
    # and no Emo-stepoperator should be set.
    for item in new_nodenet.stepoperators:
        assert 'Emotional' not in item.__class__.__name__


def test_modulators_sensor_actuator_connection(runtime, test_nodenet, test_world):
    nodenet = runtime.get_nodenet(test_nodenet)
    runtime.set_nodenet_properties(test_nodenet, worldadapter="Braitenberg", world_uid=test_world)
    res, s1_id = runtime.add_node(test_nodenet, "Sensor", [10, 10], None, name="brightness_l", parameters={'datasource': 'brightness_l'})
    res, s2_id = runtime.add_node(test_nodenet, "Sensor", [20, 20], None, name="emo_activation", parameters={'datasource': 'emo_activation'})
    res, a1_id = runtime.add_node(test_nodenet, "Actuator", [30, 30], None, name="engine_l", parameters={'datatarget': 'engine_l'})
    res, a2_id = runtime.add_node(test_nodenet, "Actuator", [40, 40], None, name="base_importance_of_intention", parameters={'datatarget': 'base_importance_of_intention'})
    res, r1_id = runtime.add_node(test_nodenet, "Register", [10, 30], None, name="r1")
    res, r2_id = runtime.add_node(test_nodenet, "Register", [10, 30], None, name="r2")
    s1 = nodenet.get_node(s1_id)
    s2 = nodenet.get_node(s2_id)
    r1 = nodenet.get_node(r1_id)
    r2 = nodenet.get_node(r2_id)
    runtime.add_link(test_nodenet, r1_id, 'gen', a1_id, 'gen')
    runtime.add_link(test_nodenet, r2_id, 'gen', a2_id, 'gen')
    r1.activation = 0.3
    r2.activation = 0.7
    emo_val = nodenet.get_modulator("emo_activation")

    # patch reset method, to check if datatarget was written
    def nothing():
        pass
    nodenet.worldadapter_instance.reset_datatargets = nothing

    nodenet.step()
    assert round(nodenet.worldadapter_instance.datatargets['engine_l'], 3) == 0.3
    assert round(s1.activation, 3) == round(nodenet.worldadapter_instance.get_datasource_value('brightness_l'), 3)
    assert round(s2.activation, 3) == round(emo_val, 3)
    assert round(nodenet.get_modulator('base_importance_of_intention'), 3) == 0.7
    assert round(nodenet.worldadapter_instance.datatargets['engine_l'], 3) == 0.3
    emo_val = nodenet.get_modulator("emo_activation")
    nodenet.step()
    assert round(s2.activation, 3) == round(emo_val, 3)


def test_node_parameters(runtime, test_nodenet, resourcepath):
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "gatetypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc",
            "parameters": ["linktype", "threshold", "protocol_mode"],
            "parameter_values": {
                "linktype": ["catexp", "subsur"],
                "protocol_mode": ["all_active", "most_active_one"]
            },
            "parameter_defaults": {
                "linktype": "catexp",
                "protocol_mode": "all_active"
            }}
        }""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    return 17")

    assert runtime.reload_native_modules()
    res, uid = runtime.add_node(test_nodenet, "Testnode", [10, 10], name="Test", parameters={"threshold": "", "protocol_mode": "most_active_one"})
    # nativemodule = runtime.nodenets[test_nodenet].get_node(uid)
    assert runtime.save_nodenet(test_nodenet)
    node = runtime.nodenets[test_nodenet].get_node(uid)
    assert node.get_parameter('linktype') == 'catexp'
    assert node.get_parameter('protocol_mode') == 'most_active_one'


def test_delete_linked_nodes(runtime, test_nodenet):

    nodenet = runtime.get_nodenet(test_nodenet)
    netapi = nodenet.netapi

    # create all evil (there will never be another dawn)
    root_of_all_evil = netapi.create_node("Pipe", None)
    evil_one = netapi.create_node("Pipe", None)
    evil_two = netapi.create_node("Pipe", None)

    netapi.link_with_reciprocal(root_of_all_evil, evil_one, "subsur")
    netapi.link_with_reciprocal(root_of_all_evil, evil_two, "subsur")

    for link in evil_one.get_gate("sub").get_links():
        link.source_node.name  # touch of evil
        link.target_node.name  # touch of evil

    for link in evil_two.get_gate("sur").get_links():
        link.source_node.name  # touch of evil
        link.target_node.name  # touch of evil

    # and the name of the horse was death
    netapi.delete_node(root_of_all_evil)
    netapi.delete_node(evil_one)
    netapi.delete_node(evil_two)


def test_multiple_nodenet_interference(runtime, engine, resourcepath):
    import os
    nodetype_file = os.path.join(resourcepath, 'Test', 'nodetypes.json')
    nodefunc_file = os.path.join(resourcepath, 'Test', 'nodefunctions.py')
    with open(nodetype_file, 'w') as fp:
        fp.write("""{"Testnode": {
            "name": "Testnode",
            "slottypes": ["gen", "foo", "bar"],
            "gatetypes": ["gen", "foo", "bar"],
            "nodefunction_name": "testnodefunc"
        }}""")
    with open(nodefunc_file, 'w') as fp:
        fp.write("def testnodefunc(netapi, node=None, **prams):\r\n    node.get_gate('gen').gate_function(17)")

    runtime.reload_native_modules()

    result, n1_uid = runtime.new_nodenet('Net1', engine=engine, owner='Pytest User')
    result, n2_uid = runtime.new_nodenet('Net2', engine=engine, owner='Pytest User')

    n1 = runtime.nodenets[n1_uid]
    n2 = runtime.nodenets[n2_uid]

    nativemodule = n1.netapi.create_node("Testnode", None, "Testnode")
    register1 = n1.netapi.create_node("Register", None, "Register1")
    n1.netapi.link(nativemodule, 'gen', register1, 'gen', weight=1.2)

    source2 = n2.netapi.create_node("Register", None, "Source2")
    register2 = n2.netapi.create_node("Register", None, "Register2")
    n2.netapi.link(source2, 'gen', source2, 'gen')
    n2.netapi.link(source2, 'gen', register2, 'gen', weight=0.9)
    source2.activation = 0.7

    runtime.step_nodenet(n2.uid)

    assert n1.current_step == 0
    assert register1.activation == 0
    assert register1.name == "Register1"
    assert nativemodule.name == "Testnode"
    assert round(register1.get_slot('gen').get_links()[0].weight, 2) == 1.2
    assert register1.get_slot('gen').get_links()[0].source_node.name == 'Testnode'
    assert n1.get_node(register1.uid).name == "Register1"

    assert n2.current_step == 1
    assert round(source2.activation, 2) == 0.7
    assert round(register2.activation, 2) == 0.63
    assert register2.name == "Register2"
    assert source2.name == "Source2"
    assert round(register2.get_slot('gen').get_links()[0].weight, 2) == 0.9
    assert register2.get_slot('gen').get_links()[0].source_node.name == 'Source2'
    assert n2.get_node(register2.uid).name == "Register2"


def test_get_nodespace_changes(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    net.step()
    result = runtime.get_nodespace_changes(test_nodenet, [None], 0)
    assert set(result['nodes_dirty'].keys()) == set(net.get_node_uids())
    assert result['nodes_deleted'] == []
    assert result['nodespaces_dirty'] == {}
    assert result['nodespaces_deleted'] == []
    net.netapi.unlink(source, 'gen', register, 'gen')
    net.netapi.delete_node(register)
    newnode = net.netapi.create_node('Register', None, "new thing")
    net.netapi.link(newnode, 'gen', source, 'gen')
    newspace = net.netapi.create_nodespace(None, "nodespace")
    net.step()
    test = runtime.get_nodenet_activation_data(test_nodenet, [None], 1)
    assert test['has_changes']
    result = runtime.get_nodespace_changes(test_nodenet, [None], 1)
    assert register.uid in result['nodes_deleted']
    assert source.uid in result['nodes_dirty']
    assert newnode.uid in result['nodes_dirty']
    assert len(result['nodes_dirty'][source.uid]['links']) == 1
    assert len(result['nodes_dirty'][newnode.uid]['links']['gen']) == 1
    assert newspace.uid in result['nodespaces_dirty']
    assert len(result['nodes_dirty'].keys()) == 2
    assert len(result['nodespaces_dirty'].keys()) == 1
    net.step()
    test = runtime.get_nodenet_activation_data(test_nodenet, [None], 2)
    assert not test['has_changes']


def test_get_nodespace_changes_cycles(runtime, test_nodenet):
    net, netapi, source, register = prepare(runtime, test_nodenet)
    net.step()
    net.netapi.delete_node(register)
    net.step()
    result = runtime.get_nodespace_changes(test_nodenet, [None], 1)
    assert register.uid in result['nodes_deleted']
    for i in range(101):
        net.step()
    result = runtime.get_nodespace_changes(test_nodenet, [None], 1)
    assert register.uid not in result['nodes_deleted']


def test_nodespace_properties(runtime, test_nodenet):
    data = {'testvalue': 'foobar'}
    rootns = runtime.get_nodenet(test_nodenet).get_nodespace(None)
    runtime.set_nodespace_properties(test_nodenet, rootns.uid, data)
    assert runtime.nodenets[test_nodenet].metadata['nodespace_ui_properties'][rootns.uid] == data
    assert runtime.get_nodespace_properties(test_nodenet, rootns.uid) == data
    runtime.save_nodenet(test_nodenet)
    runtime.revert_nodenet(test_nodenet)
    assert runtime.get_nodespace_properties(test_nodenet, rootns.uid) == data
    properties = runtime.get_nodespace_properties(test_nodenet)
    assert properties[rootns.uid] == data
