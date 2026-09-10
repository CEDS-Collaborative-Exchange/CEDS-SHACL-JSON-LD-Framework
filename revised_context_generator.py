from lxml import etree as ET
import csv
import json
import re

# Define namespaces
namespaces = {
    'ceds': "https://w3id.org/CEDStandards/terms/",
    'dc': "http://purl.org/dc/elements/1.1/",
    'owl': "http://www.w3.org/2002/07/owl#",
    'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    'xml': "http://www.w3.org/XML/1998/namespace",
    'xsd': "http://www.w3.org/2001/XMLSchema#",
    'rdfs': "http://www.w3.org/2000/01/rdf-schema#",
    'skos': "http://www.w3.org/2004/02/skos/core#",
    'schema': "http://schema.org/"
}

# Path to your XML file
xml_file = "C:\\Repos\\CEDS-Ontology\\src\\CEDS-Ontology.rdf"

# Parse the XML file
tree = ET.parse(xml_file)
root = tree.getroot()

# Register namespaces
for prefix, uri in namespaces.items():
    ET.register_namespace(prefix, uri)

def create_human_readable_alias(skos_notation, rdfs_label=None):
    """
    Create a human-readable alias from SKOS notation and label
    """
    if rdfs_label:
        # Use the label if available, clean it up for JSON-LD
        alias = rdfs_label.strip()
        # Replace spaces and special characters, but preserve meaningful structure
        alias = re.sub(r'\s+', '', alias)  # Remove spaces
        alias = re.sub(r'[^\w]', '', alias)  # Remove non-word characters
        
        # Ensure it starts with a letter (JSON-LD requirement)
        if alias and not alias[0].isalpha():
            alias = f"Value{alias}"
            
        return alias if alias else f"Value{skos_notation.replace('/', '_')}"
    else:
        # Fallback to a cleaned version of the notation
        clean_notation = skos_notation.replace('/', '_').replace('-', '_')
        return f"Value{clean_notation}"

def is_enumeration_property(property_node, dc_identifier_value):
    """
    Determine if a property should use @vocab type coercion
    This is based on whether the property has a range that contains Named Individuals
    """
    rdfs_range = property_node.find("rdfs:range", namespaces)
    if rdfs_range is not None:
        range_resource = rdfs_range.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
        if range_resource:
            # Look for Named Individuals that reference this range class via skos:inScheme
            individuals = root.findall(f".//owl:NamedIndividual[skos:inScheme[@rdf:resource='{range_resource}']]", namespaces)
            if len(individuals) > 0:
                return True
    
    # Alternative check: look for properties that commonly reference enumerations
    # You can customize this list based on your CEDS ontology patterns
    enumeration_patterns = [
        'has', 'type', 'status', 'category', 'level', 'system', 'method', 'code'
    ]
    
    property_notation = property_node.find("skos:notation", namespaces)
    if property_notation is not None:
        notation_text = property_notation.text.lower()
        for pattern in enumeration_patterns:
            if pattern in notation_text:
                return True
    
    return False

######## Creates the CEDS Context with Enumeration Aliases
print("Processing CEDS ontology for enhanced context generation...")

# Create dictionaries to store different types of mappings
json_ld_data = {}
regular_aliases = {}
enumeration_properties = {}
enumeration_aliases = {}

# Base context - same as your original
json_ld_data["@context"] = {
    "@vocab": "https://w3id.org/CEDStandards/terms/",
    "@base": "https://w3id.org/CEDStandards/terms/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ceds": "https://w3id.org/CEDStandards/terms/",
    "schema": "http://schema.org/"
}

print("Pass 1: Processing properties and classes...")

# Iterate through the root level nodes - enhanced from your original logic
for node in root:
    skos_notation = node.find("skos:notation", namespaces)
    dc_identifier = node.find("dc:identifier", namespaces)
    rdfs_label = node.find("rdfs:label", namespaces)
    
    if skos_notation is not None and dc_identifier is not None:
        skos_value = skos_notation.text
        dc_value = dc_identifier.text
        label_text = rdfs_label.text if rdfs_label is not None else None
        
        # Handle different node types - preserving your original logic
        if node.tag != "{http://www.w3.org/2002/07/owl#}NamedIndividual":
            # This is a property or class
            
            # Check if this is an ObjectProperty that should use @vocab
            if (node.tag == "{http://www.w3.org/2002/07/owl#}ObjectProperty" and 
                is_enumeration_property(node, dc_value)):
                
                print(f"  Found enumeration property: {skos_value} -> {dc_value}")
                enumeration_properties[skos_value] = {
                    "@id": dc_value,
                    "@type": "@vocab"  # This enables human-readable enumeration aliases
                }
            else:
                # Regular property or class - use your original logic
                regular_aliases[skos_value] = dc_value
                
        else:
            # This is a Named Individual (enumeration value) - enhanced from your original
            skos_in_scheme = node.find("skos:inScheme", namespaces)
            if skos_in_scheme is not None:
                parent_iri = skos_in_scheme.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
                parent_node = root.find(f".//*[@rdf:about='{parent_iri}']", namespaces)
                if parent_node is not None:
                    parent_skos_notation = parent_node.find("skos:notation", namespaces)
                    if parent_skos_notation is not None:
                        parent_skos_value = parent_skos_notation.text
                        full_skos_value = f"{parent_skos_value}_{skos_value}"
                        
                        # Create human-readable alias from the label
                        if label_text:
                            human_alias = create_human_readable_alias(skos_value, label_text)
                            enumeration_aliases[human_alias] = dc_value
                            print(f"  Created enumeration alias: {human_alias} -> {dc_value}")
                        
                        # Also keep the original notation-based mapping for backwards compatibility
                        original_alias = full_skos_value.replace('/', '_')
                        enumeration_aliases[original_alias] = dc_value

print(f"\nPass 2: Building final context...")

# Combine all mappings into the final context - order matters
json_ld_data["@context"].update(regular_aliases)        # Regular properties and classes
json_ld_data["@context"].update(enumeration_properties) # Properties with @vocab type coercion  
json_ld_data["@context"].update(enumeration_aliases)    # Human-readable enumeration aliases

print(f"Context generation summary:")
print(f"  - Regular aliases: {len(regular_aliases)}")
print(f"  - Enumeration properties: {len(enumeration_properties)}")
print(f"  - Enumeration aliases: {len(enumeration_aliases)}")

# Show examples of what was generated
if enumeration_properties:
    print(f"\nSample enumeration properties (using @vocab):")
    count = 0
    for prop_name, prop_def in enumeration_properties.items():
        if count < 5:
            print(f"  {prop_name}: {prop_def}")
            count += 1

if enumeration_aliases:
    print(f"\nSample enumeration aliases:")
    count = 0 
    for alias, target_id in enumeration_aliases.items():
        if count < 10:
            print(f"  {alias} -> {target_id}")
            count += 1

# Write the main context file - same path as your original
json_ld_file = "C:\\Repos\\CEDS-JSON-JSON-LD-Framework\\src\\context.json"

with open(json_ld_file, "w", encoding="utf-8") as f:
    json.dump(json_ld_data, f, indent=4)

print(f"\n✅ Enhanced context file written to: {json_ld_file}")

# Create additional reference files for documentation
enumeration_reference = {
    "description": "CEDS Enumeration Aliases for Human-Readable JSON-LD",
    "usage_instructions": {
        "old_way": '{"hasGradeLevel": {"@id": "ceds:NI000206012348"}}',
        "new_way": '{"hasGradeLevel": "Grade03"}',
        "note": "Both approaches produce identical RDF output"
    },
    "enumeration_properties": {
        prop_name: prop_def for prop_name, prop_def in enumeration_properties.items()
    },
    "enumeration_aliases": enumeration_aliases
}

reference_file = "C:\\Repos\\CEDS-JSON-JSON-LD-Framework\\src\\enumeration_reference.json"
with open(reference_file, "w", encoding="utf-8") as f:
    json.dump(enumeration_reference, f, indent=4)

print(f"📚 Enumeration reference written to: {reference_file}")

# Create a usage example
if enumeration_properties and enumeration_aliases:
    example_data = {
        "@context": "./context.json",
        "@id": "example:ceds-record-001",
        "@type": "Student",
        "_comment": "Example showing human-readable enumeration usage"
    }
    
    # Add examples using the first few enumeration properties and aliases
    prop_count = 0
    for prop_name in enumeration_properties.keys():
        if prop_count < 3:
            # Find a suitable enumeration alias
            sample_alias = next(iter(enumeration_aliases.keys()), None)
            if sample_alias:
                example_data[prop_name] = sample_alias
                prop_count += 1

    example_file = "C:\\Repos\\CEDS-JSON-JSON-LD-Framework\\src\\usage_example.json"
    with open(example_file, "w", encoding="utf-8") as f:
        json.dump(example_data, f, indent=4)
    
    print(f"📝 Usage example written to: {example_file}")

print(f"\n🎉 Enhanced CEDS context generation complete!")
print(f"\nYour JSON-LD can now use human-readable enumeration values like:")
if enumeration_aliases:
    sample_alias = next(iter(enumeration_aliases.keys()))
    print(f'  "someProperty": "{sample_alias}"')
    print(f"instead of:")
    print(f'  "someProperty": {{"@id": "ceds:{enumeration_aliases[sample_alias]}"}}')
