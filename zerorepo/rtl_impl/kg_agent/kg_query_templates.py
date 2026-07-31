GET_CHILD_MODULE_CONTEXT = """
MATCH (parent:Module {repo_uid: $repo_uid, name: $parent_module})-[:INSTANTIATES]->(inst:Instance)
OPTIONAL MATCH (inst)-[:OF_MODULE]->(child:Module)
OPTIONAL MATCH (child)-[:HAS]->(port:Port)
OPTIONAL MATCH (child)-[:HAS_SIM_RESULT]->(sim:SimulationResult)
WITH parent, inst, child, sim, collect(DISTINCT {
  name: port.name,
  attrs: port.attrs,
  path: port.path,
  sl: port.sl,
  el: port.el
}) AS ports
RETURN parent.name AS parent_module,
       inst.name AS instance_name,
       inst.attrs AS instance_attrs,
       child.name AS child_module,
       child.path AS child_path,
       child.sl AS child_start_line,
       child.el AS child_end_line,
       ports AS child_ports,
       sim.status AS simulation_status,
       sim.passed AS simulation_passed,
       sim.final_rtl_path AS final_rtl_path
ORDER BY instance_name, child_module
"""


GET_MODULE_INTERFACE = """
MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
OPTIONAL MATCH (m)-[:HAS]->(p:Port)
OPTIONAL MATCH (m)-[:HAS]->(param:Param)
OPTIONAL MATCH (m)-[:HAS_SIM_RESULT]->(sim:SimulationResult)
RETURN m.name AS module,
       m.path AS module_path,
       m.sl AS module_start_line,
       m.el AS module_end_line,
       sim.status AS simulation_status,
       sim.passed AS simulation_passed,
       sim.final_rtl_path AS final_rtl_path,
       collect(DISTINCT {
         name: p.name,
         attrs: p.attrs,
         path: p.path,
         sl: p.sl,
         el: p.el
       }) AS ports,
       collect(DISTINCT {
         name: param.name,
         attrs: param.attrs,
         path: param.path,
         sl: param.sl,
         el: param.el
       }) AS parameters
"""


GET_INSTANCE_CONTEXT = """
MATCH (parent:Module {repo_uid: $repo_uid, name: $parent_module})-[:INSTANTIATES]->(inst:Instance)
OPTIONAL MATCH (inst)-[:OF_MODULE]->(child:Module)
OPTIONAL MATCH (inst)-[conn:CONNECTS]->(target)
WHERE ($child_module = "" OR child.name = $child_module OR inst.attrs CONTAINS $child_module)
  AND ($instance_name = "" OR inst.name = $instance_name)
RETURN parent.name AS parent_module,
       inst.name AS instance_name,
       inst.path AS instance_path,
       inst.sl AS instance_start_line,
       inst.el AS instance_end_line,
       inst.attrs AS instance_attrs,
       child.name AS child_module,
       child.path AS child_path,
       collect(DISTINCT {
         rel: properties(conn),
         target_kind: target.kind,
         target_name: target.name,
         target_attrs: target.attrs,
         target_path: target.path,
         target_sl: target.sl,
         target_el: target.el
       }) AS connections
ORDER BY instance_name
"""


GET_SIGNAL_DEBUG_CONTEXT = """
MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
OPTIONAL MATCH (m)-[:HAS]->(sym)
WHERE sym.kind IN ["Port", "Signal"] AND sym.name = $signal_name
OPTIONAL MATCH (driver)-[:DRIVES]->(sym)
RETURN m.name AS module,
       sym.kind AS symbol_kind,
       sym.name AS signal_name,
       sym.path AS signal_path,
       sym.sl AS signal_start_line,
       sym.el AS signal_end_line,
       sym.attrs AS signal_attrs,
       collect(DISTINCT {
         kind: driver.kind,
         name: driver.name,
         path: driver.path,
         sl: driver.sl,
         el: driver.el,
         attrs: driver.attrs
       }) AS drivers
"""


GET_MODULE_NEIGHBORS = """
MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})-[:INSTANTIATES]->(inst:Instance)
OPTIONAL MATCH (inst)-[:OF_MODULE]->(other:Module)
RETURN "child" AS relation,
       m.name AS module,
       inst.name AS instance_name,
       inst.path AS instance_path,
       other.name AS related_module
UNION
MATCH (other:Module)-[:INSTANTIATES]->(inst:Instance)-[:OF_MODULE]->(m:Module {repo_uid: $repo_uid, name: $module_name})
RETURN "parent" AS relation,
       m.name AS module,
       inst.name AS instance_name,
       inst.path AS instance_path,
       other.name AS related_module
"""


GET_SIGNAL_BOUNDARY_MAPPINGS = """
MATCH (parent:Module {repo_uid: $repo_uid, name: $module_name})-[:INSTANTIATES]->(inst:Instance)
MATCH (inst)-[:OF_MODULE]->(child:Module)
MATCH (inst)-[conn:CONNECTS]->(target)
OPTIONAL MATCH (child)-[:HAS]->(port:Port)
WHERE port.name = conn.p
RETURN "parent_to_child" AS mapping_direction,
       parent.name AS parent_module,
       inst.name AS instance_name,
       inst.path AS instance_path,
       child.name AS child_module,
       conn.p AS child_port,
       port.attrs AS child_port_attrs,
       port.path AS child_port_path,
       target.kind AS target_kind,
       target.name AS target_name,
       target.attrs AS target_attrs,
       conn.x AS connection_expression,
       properties(conn) AS connection
UNION
MATCH (parent:Module)-[:INSTANTIATES]->(inst:Instance)-[:OF_MODULE]->(child:Module {repo_uid: $repo_uid, name: $module_name})
MATCH (inst)-[conn:CONNECTS]->(target)
OPTIONAL MATCH (child)-[:HAS]->(port:Port)
WHERE port.name = conn.p
RETURN "child_to_parent" AS mapping_direction,
       parent.name AS parent_module,
       inst.name AS instance_name,
       inst.path AS instance_path,
       child.name AS child_module,
       conn.p AS child_port,
       port.attrs AS child_port_attrs,
       port.path AS child_port_path,
       target.kind AS target_kind,
       target.name AS target_name,
       target.attrs AS target_attrs,
       conn.x AS connection_expression,
       properties(conn) AS connection
"""


GET_MODULE_SOURCE = """
MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
RETURN m.name AS module,
       m.actual_path AS actual_path,
       m.path AS path,
       m.sl AS module_start_line,
       m.el AS module_end_line,
       m.uid AS module_uid
"""


GET_FAILURE_MODULE_STATUS = """
MATCH (m:Module {repo_uid: $repo_uid, name: $module_name})
OPTIONAL MATCH (m)-[:HAS_SIM_RESULT]->(sim:SimulationResult)
RETURN m.name AS module,
       m.path AS module_path,
       sim.status AS simulation_status,
       sim.passed AS simulation_passed,
       sim.mismatch_count AS mismatch_count,
       sim.reason AS reason,
       sim.trace_report_path AS trace_report_path,
       sim.sim_output_path AS sim_output_path
"""
