from lxml import etree as ET
import csv
import json
import re

# Define namespaces
namespaces = {
    'ceds': "http://ceds.ed.gov/terms#",
    'dc': "http://purl.org/dc/elements/1.1/",
    'owl': "http://www.w3.org/2002/07/owl#",
    'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    'xml': "http://www.w3.org/XML/1998/namespace",
    'xsd': "http://www.w3.org/2001/XMLSchema#",
    'rdfs': "http://www.w3.org/2000/01/rdf-schema#",
    'skos': "http://www.w3.org/2004/02/skos/core#",
    'schema': "https://schema.org/"
}

# Path to your XML file
xml_file = "C:\\Repos\\CEDS-Ontology\\src\\CEDS-Ontology.rdf"

# Parse the XML file
tree = ET.parse(xml_file)
root = tree.getroot()

# Register namespaces
for prefix, uri in namespaces.items():
    ET.register_namespace(prefix, uri)

def is_enumeration_property(node, namespaces):
    """
    Determine if a property should use @vocab type coercion (i.e., it references enumerations)
    This checks if the property has a range that points to a class with enumeration individuals
    """
    schema_range = node.find("schema:rangeIncludes", namespaces)
    if schema_range is not None:
        range_resource = schema_range.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
        enum_class = root.findall(f".//owl:Class[@rdf:about='{range_resource}']", namespaces)

        if range_resource and enum_class:
            # This is an enumeration class (C0xxxxx), check if it has named individuals
            class_iri = range_resource
            individuals = root.findall(f".//owl:NamedIndividual/skos:inScheme[@rdf:resource='{class_iri}']", namespaces)
            return len(individuals) > 0
    return False

######## Creates the CEDS Context with Enumeration Aliases
# Create separate dictionaries for different types
data_properties = {}
classes = {}
enumeration_properties = {}
enumeration_aliases = {}

# Base context - hard-coded contexts first
context = {
    "@vocab": "http://ceds.ed.gov/terms#",
    "@base": "http://ceds.ed.gov/terms#", 
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ceds": "http://ceds.ed.gov/terms#",
    "schema": "http://schema.org/"
}

print("Processing CEDS ontology for context generation...")

# First pass: Collect all properties and identify enumeration properties
print("Pass 1: Identifying properties and enumeration relationships...")
for node in root:
    skos_notation = node.find("skos:notation", namespaces)
    dc_identifier = node.find("dc:identifier", namespaces)
    rdfs_label = node.find("rdfs:label", namespaces)
    
    if skos_notation is not None and dc_identifier is not None:
        skos_value = skos_notation.text
        dc_value = dc_identifier.text
        label_text = rdfs_label.text if rdfs_label is not None else None
        
        # Handle different types of nodes based on RDF type
        if node.tag == "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Property":
            # Check schema:rangeIncludes to determine if it's an enumeration property
            if is_enumeration_property(node, namespaces):
                print(f"  Found enumeration property: {skos_value} ({dc_value})")
                enumeration_properties[skos_value] = {
                    "@id": f"ceds:{dc_value}",
                    "@type": "@vocab"
                }
            else:
                # Include as regular property if not pointing to C2 classes
                data_properties[skos_value] = f"ceds:{dc_value}"
                            
        elif node.tag == "{http://www.w3.org/2002/07/owl#}Class" or node.tag == "{http://www.w3.org/2000/01/rdf-schema#}Class":
            # Classes are included as simple mappings
            classes[skos_value] = f"ceds:{dc_value}"
            
        elif node.tag == "{http://www.w3.org/2002/07/owl#}NamedIndividual":
            # This is a named individual (enumeration value)
            skos_in_scheme = node.find("skos:inScheme", namespaces)
            if skos_in_scheme is not None:
                parent_iri = skos_in_scheme.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                parent_node = root.find(f".//*[@rdf:about='{parent_iri}']", namespaces)
                if parent_node is not None:
                    parent_skos_notation = parent_node.find("skos:notation", namespaces)
                    if parent_skos_notation is not None:
                        parent_skos_value = parent_skos_notation.text
                        # Create hierarchical notation for the enumeration
                        full_skos_value = f"{parent_skos_value}_{skos_value}"
                        
                        # Store the enumeration alias - maps human name to opaque ID
                        enumeration_aliases[full_skos_value] = f"ceds:{dc_value}"
                        print(f"  Created enumeration alias: {full_skos_value} -> ceds:{dc_value}")

# Second pass: Build final context in the correct order
print("\nPass 2: Building final context...")

# Start with hard-coded contexts, then add in order: classes, data properties, enumeration properties, enumeration aliases
final_context = context.copy()

# Add classes first
final_context.update(classes)

# Add data properties
final_context.update(data_properties)

# Add enumeration properties (with @vocab)
final_context.update(enumeration_properties)

# Add enumeration aliases
final_context.update(enumeration_aliases)

# Create final JSON-LD structure
json_ld_data = {"@context": final_context}

print(f"\nContext generation complete:")
print(f"  - Classes processed: {len(classes)}")
print(f"  - Data properties processed: {len(data_properties)}")
print(f"  - Enumeration properties identified: {len(enumeration_properties)}")
print(f"  - Enumeration values aliased: {len(enumeration_aliases)}")

# Print some examples of enumeration properties for verification
print(f"\nEnumeration properties using @vocab type coercion:")
for prop_name, prop_def in enumeration_properties.items():
    print(f"  - {prop_name}: {prop_def}")
        
print(f"\nSample enumeration aliases:")
count = 0
for alias, target in enumeration_aliases.items():
    if count < 10:  # Show first 10 examples
        print(f"  - {alias} -> {target}")
        count += 1

# Path to the output JSON-LD file  
json_ld_file = "C:\\Repos\\CEDS-JSON-JSON-LD-Framework\\src\\context.json"

# Write the JSON-LD data to the file
with open(json_ld_file, "w", encoding="utf-8") as f:
    json.dump(json_ld_data, f, indent=4)

print(f"\n✅ Context file written to: {json_ld_file}")