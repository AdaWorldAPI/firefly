"""
Firefly Ruby Compiler: Parse Ruby source into executable graph nodes.

Extracts:
- Model declarations (class X < ApplicationRecord)
- Validations (validates :x, presence: true)
- Associations (belongs_to :x, has_many :y)
- Callbacks (before_save, after_create)
- Scopes (scope :active, -> { where(active: true) })

Compiles to FireflyNodes with:
- Schema vector (WHAT)
- Logic vector (HOW)
- Context vector (WHERE)
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from core import project, random_vector, bind, bundle, ROLE_SCHEMA, ROLE_LOGIC, ROLE_CONTEXT


@dataclass
class RubyValidation:
    """Parsed Ruby validation."""
    field: str
    type: str  # presence, length, format, etc.
    options: Dict[str, Any]


@dataclass
class RubyAssociation:
    """Parsed Ruby association."""
    name: str
    type: str  # belongs_to, has_many, has_one
    options: Dict[str, Any]


@dataclass 
class RubyCallback:
    """Parsed Ruby callback."""
    timing: str  # before, after, around
    event: str   # save, create, update, destroy
    method: str


@dataclass
class RubyModel:
    """Parsed Ruby model."""
    name: str
    file_path: str
    validations: List[RubyValidation]
    associations: List[RubyAssociation]
    callbacks: List[RubyCallback]
    scopes: List[Dict[str, Any]]


class RubyParser:
    """
    Parse Ruby model files.
    
    Uses regex patterns - not a full AST parser, but good enough
    for extracting declarations.
    """
    
    # Regex patterns for Ruby constructs
    PATTERNS = {
        'class': re.compile(r'class\s+(\w+)\s*<\s*(\w+)'),
        'validates': re.compile(r'validates\s+:(\w+)(?:,\s*(.+))?$', re.MULTILINE),
        'validates_opts': re.compile(r'(\w+):\s*(?:(\{[^}]+\})|(\w+)|(\[[^\]]+\]))'),
        'belongs_to': re.compile(r'belongs_to\s+:(\w+)(?:,\s*(.+))?$', re.MULTILINE),
        'has_many': re.compile(r'has_many\s+:(\w+)(?:,\s*(.+))?$', re.MULTILINE),
        'has_one': re.compile(r'has_one\s+:(\w+)(?:,\s*(.+))?$', re.MULTILINE),
        'before_save': re.compile(r'before_save\s+:(\w+)'),
        'after_save': re.compile(r'after_save\s+:(\w+)'),
        'before_create': re.compile(r'before_create\s+:(\w+)'),
        'after_create': re.compile(r'after_create\s+:(\w+)'),
        'before_update': re.compile(r'before_update\s+:(\w+)'),
        'after_update': re.compile(r'after_update\s+:(\w+)'),
        'before_destroy': re.compile(r'before_destroy\s+:(\w+)'),
        'after_destroy': re.compile(r'after_destroy\s+:(\w+)'),
        'scope': re.compile(r'scope\s+:(\w+),\s*->.*'),
    }
    
    def parse_file(self, file_path: str) -> Optional[RubyModel]:
        """Parse a single Ruby file."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find class declaration
        class_match = self.PATTERNS['class'].search(content)
        if not class_match:
            return None
        
        class_name = class_match.group(1)
        
        return RubyModel(
            name=class_name,
            file_path=file_path,
            validations=self._parse_validations(content),
            associations=self._parse_associations(content),
            callbacks=self._parse_callbacks(content),
            scopes=self._parse_scopes(content),
        )
    
    def _parse_validations(self, content: str) -> List[RubyValidation]:
        """Extract validations from content."""
        validations = []
        
        for match in self.PATTERNS['validates'].finditer(content):
            field = match.group(1)
            opts_str = match.group(2) or ""
            
            # Parse validation options
            options = {}
            for opt_match in self.PATTERNS['validates_opts'].finditer(opts_str):
                key = opt_match.group(1)
                # Get the value (could be in different groups)
                value = opt_match.group(2) or opt_match.group(3) or opt_match.group(4) or True
                options[key] = value
            
            # Determine validation type from options
            if 'presence' in options:
                validations.append(RubyValidation(field, 'presence', options))
            if 'length' in options:
                validations.append(RubyValidation(field, 'length', options))
            if 'format' in options:
                validations.append(RubyValidation(field, 'format', options))
            if 'uniqueness' in options:
                validations.append(RubyValidation(field, 'uniqueness', options))
            if 'numericality' in options:
                validations.append(RubyValidation(field, 'numericality', options))
            
            # If no specific type, it's a generic validation
            if not validations or validations[-1].field != field:
                validations.append(RubyValidation(field, 'custom', options))
        
        return validations
    
    def _parse_associations(self, content: str) -> List[RubyAssociation]:
        """Extract associations from content."""
        associations = []
        
        for assoc_type in ['belongs_to', 'has_many', 'has_one']:
            for match in self.PATTERNS[assoc_type].finditer(content):
                name = match.group(1)
                opts_str = match.group(2) or ""
                
                # Parse options
                options = {}
                for opt_match in self.PATTERNS['validates_opts'].finditer(opts_str):
                    key = opt_match.group(1)
                    value = opt_match.group(2) or opt_match.group(3) or True
                    options[key] = value
                
                associations.append(RubyAssociation(name, assoc_type, options))
        
        return associations
    
    def _parse_callbacks(self, content: str) -> List[RubyCallback]:
        """Extract callbacks from content."""
        callbacks = []
        
        callback_patterns = [
            ('before', 'save'), ('after', 'save'),
            ('before', 'create'), ('after', 'create'),
            ('before', 'update'), ('after', 'update'),
            ('before', 'destroy'), ('after', 'destroy'),
        ]
        
        for timing, event in callback_patterns:
            pattern_key = f"{timing}_{event}"
            for match in self.PATTERNS[pattern_key].finditer(content):
                method = match.group(1)
                callbacks.append(RubyCallback(timing, event, method))
        
        return callbacks
    
    def _parse_scopes(self, content: str) -> List[Dict[str, Any]]:
        """Extract scopes from content."""
        scopes = []
        
        for match in self.PATTERNS['scope'].finditer(content):
            scope_name = match.group(1)
            scopes.append({"name": scope_name, "raw": match.group(0)})
        
        return scopes


class RubyCompiler:
    """
    Compile parsed Ruby models into Firefly graphs.
    """
    
    def __init__(self, embed_fn=None):
        """
        Initialize compiler.
        
        Args:
            embed_fn: Optional function to embed text (for semantic vectors).
                      If None, uses random vectors.
        """
        self.parser = RubyParser()
        self.embed_fn = embed_fn
    
    async def compile_directory(self, path: str) -> Tuple[List[FireflyNode], List[FireflyEdge]]:
        """
        Compile all Ruby models in a directory.
        
        Returns nodes and edges for the compiled graph.
        """
        all_nodes = []
        all_edges = []
        
        # Find all .rb files
        path = Path(path)
        rb_files = list(path.rglob("*.rb"))
        
        print(f"🔥 Found {len(rb_files)} Ruby files")
        
        for rb_file in rb_files:
            # Skip non-model files
            if 'spec' in str(rb_file) or 'test' in str(rb_file):
                continue
            
            model = self.parser.parse_file(str(rb_file))
            if model:
                nodes, edges = await self._compile_model(model)
                all_nodes.extend(nodes)
                all_edges.extend(edges)
                print(f"   Compiled {model.name}: {len(nodes)} nodes, {len(edges)} edges")
        
        return all_nodes, all_edges
    
    async def _compile_model(self, model: RubyModel) -> Tuple[List[FireflyNode], List[FireflyEdge]]:
        """Compile a single model into nodes and edges."""
        nodes = []
        edges = []
        
        # Create entry points for each operation
        for operation in ['create', 'update', 'destroy']:
            entry = await self._create_entry_node(model.name, operation)
            nodes.append(entry)
        
        # Compile validations
        prev_node = None
        for i, validation in enumerate(model.validations):
            node = await self._compile_validation(model.name, validation, i)
            nodes.append(node)
            
            # Connect to previous node or entry
            if prev_node:
                edge = FireflyEdge.from_nodes(prev_node, node, type="FEEDS")
                edges.append(edge)
            else:
                # Connect to create entry
                entry = nodes[0]  # create entry
                edge = FireflyEdge.from_nodes(entry, node, type="TRIGGERS")
                edges.append(edge)
            
            prev_node = node
        
        # Compile callbacks
        for callback in model.callbacks:
            node = await self._compile_callback(model.name, callback)
            nodes.append(node)
            
            # Connect based on timing
            # TODO: More sophisticated edge creation
            if prev_node:
                edge = FireflyEdge.from_nodes(prev_node, node, type="TRIGGERS")
                edges.append(edge)
                prev_node = node
        
        # Create persist node
        persist = await self._create_persist_node(model.name)
        nodes.append(persist)
        
        if prev_node:
            edge = FireflyEdge.from_nodes(prev_node, persist, type="FEEDS")
            edges.append(edge)
        
        return nodes, edges
    
    async def _create_entry_node(self, model_name: str, operation: str) -> FireflyNode:
        """Create entry point node for an operation."""
        node_id = f"{model_name}_{operation}_entry"
        
        schema_desc = f"Entry point for {model_name}.{operation}"
        logic_desc = f"Initialize {operation} operation context"
        context_desc = f"Start of {operation} flow for {model_name}"
        
        return await self._create_node(
            node_id,
            schema_desc,
            logic_desc,
            context_desc,
            type="TRIGGER",
            fn_name="transform_identity",
        )
    
    async def _compile_validation(
        self, 
        model_name: str, 
        validation: RubyValidation,
        index: int
    ) -> FireflyNode:
        """Compile a validation into a node."""
        node_id = f"{model_name}_validate_{validation.field}_{validation.type}_{index}"
        
        schema_desc = f"Input: {validation.field} (any), Output: valid (bool), errors (string[])"
        logic_desc = self._describe_validation(validation)
        context_desc = f"Validation phase for {model_name}, validates {validation.field}"
        
        # Determine executor
        fn_name = f"validate_{validation.type}"
        if validation.type not in ['presence', 'length']:
            fn_name = "validate_presence"  # Fallback
        
        return await self._create_node(
            node_id,
            schema_desc,
            logic_desc,
            context_desc,
            type="VALIDATE",
            fn_name=fn_name,
            input_schema={validation.field: "any"},
            output_schema={"valid": "bool", "errors": "string[]"},
        )
    
    def _describe_validation(self, validation: RubyValidation) -> str:
        """Generate logic description for validation."""
        if validation.type == 'presence':
            return f"Check that {validation.field} is not null or empty"
        elif validation.type == 'length':
            parts = [f"Check {validation.field} length"]
            if 'minimum' in validation.options:
                parts.append(f"minimum {validation.options['minimum']}")
            if 'maximum' in validation.options:
                parts.append(f"maximum {validation.options['maximum']}")
            return ", ".join(parts)
        elif validation.type == 'format':
            return f"Check {validation.field} matches format pattern"
        elif validation.type == 'uniqueness':
            return f"Check {validation.field} is unique in database"
        else:
            return f"Custom validation for {validation.field}"
    
    async def _compile_callback(self, model_name: str, callback: RubyCallback) -> FireflyNode:
        """Compile a callback into a node."""
        node_id = f"{model_name}_{callback.timing}_{callback.event}_{callback.method}"
        
        schema_desc = f"Callback: {callback.timing}_{callback.event}"
        logic_desc = f"Execute {callback.method} {callback.timing} {callback.event}"
        context_desc = f"{callback.timing.title()} {callback.event} callback for {model_name}"
        
        return await self._create_node(
            node_id,
            schema_desc,
            logic_desc,
            context_desc,
            type="TRIGGER",
            fn_name=callback.method,
        )
    
    async def _create_persist_node(self, model_name: str) -> FireflyNode:
        """Create persistence node."""
        node_id = f"{model_name}_persist"
        
        schema_desc = f"Input: {model_name} attributes, Output: saved {model_name}"
        logic_desc = f"Insert or update {model_name} in database"
        context_desc = f"Persistence phase for {model_name}"
        
        return await self._create_node(
            node_id,
            schema_desc,
            logic_desc,
            context_desc,
            type="PERSIST",
            fn_name=f"persist_{model_name.lower()}",
        )
    
    async def _create_node(
        self,
        node_id: str,
        schema_desc: str,
        logic_desc: str,
        context_desc: str,
        **kwargs
    ) -> FireflyNode:
        """Create a node with semantic vectors."""
        
        # Generate vectors
        if self.embed_fn:
            # Use real embeddings
            schema_vec = project(await self.embed_fn(schema_desc))
            logic_vec = project(await self.embed_fn(logic_desc))
            context_vec = project(await self.embed_fn(context_desc))
        else:
            # Use deterministic vectors from descriptions
            import hashlib
            def hash_to_vec(s: str) -> bytes:
                h = hashlib.sha256(s.encode()).digest()
                return (h * 40)[:1250]
            
            schema_vec = hash_to_vec(schema_desc)
            logic_vec = hash_to_vec(logic_desc)
            context_vec = hash_to_vec(context_desc)
        
        return FireflyNode.from_components(
            id=node_id,
            schema_vec=schema_vec,
            logic_vec=logic_vec,
            context_vec=context_vec,
            **kwargs
        )
