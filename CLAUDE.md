# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Slitherlink3D is an interactive 3D puzzle game that brings the classic Slitherlink puzzle to polyhedral surfaces. Players solve puzzles by drawing loops on the edges of 3D polyhedra (dodecahedrons, cubes) following traditional Slitherlink rules. The project uses Three.js for 3D rendering and is structured as a client-side web application.

## Development Commands

This is a client-side JavaScript application that runs directly in the browser with no build process required:

- **Run the application**: Open `main.html` in a web browser or serve via a local web server
- **Local development server**: `python3 -m http.server 8000` (or any static file server)
- **No build, test, or lint commands** - this is a pure client-side application

## Architecture Overview

### Core Architecture Pattern
The application follows a modular ES6 approach with clear separation of concerns:

- **main.js**: Entry point that orchestrates scene creation, camera setup, and render loop
- **scene.js**: Scene factory that creates and configures all 3D objects and lighting
- **Grid.js**: Graph-based data structure representing polyhedron topology (vertices, edges, faces)
- **interaction.js**: Handles user input for face highlighting and edge state cycling
- **geometry.js**: Creates Three.js geometries for polyhedra (cube, dodecahedron) and converts them to Grid format

### Key Data Structures

**Grid Class**: Central data structure that maintains the puzzle state
- Maps of vertices, edges, and faces with their relationships
- Each edge has a state: 'unknown', 'filledIn', or 'ruledOut'
- Faces can be highlighted for debugging/interaction

**Face/Vertex Mapping**: Critical for interaction
- `faceMap`: Maps geometry triangle indices to face IDs for raycasting
- `faceVertexRanges`: Maps face IDs to vertex ranges in geometry for color updates

### Module Dependencies
```
main.js
├── scene.js
│   ├── geometry.js (createCube, createDodecahedron)
│   ├── skybox.js
│   └── textRenderer.js
├── interaction.js
└── constants.js
```

## File Organization

- **js/**: All JavaScript modules
  - Core game logic: Grid.js, Face.js, Edge.js, Vertex.js
  - Rendering: scene.js, geometry.js, skybox.js, textRenderer.js
  - User input: interaction.js
  - Configuration: constants.js
- **data/**: JSON files containing polyhedron geometry and puzzle data
- **ideas/**: Development notes and TODOs
- **slitherlink3D-old/**: Legacy codebase from previous iterations

## Data Formats

**JSON Polyhedron Format** (data/*.json):
```json
{
  "id": "testCube",
  "name": "testCube",
  "vertices": [[x,y,z], ...],
  "cells": [[v1,v2,v3,v4], ...],
  "puzzles": []
}
```

## Key Implementation Details

- **Three.js version**: 0.128.0 (loaded via CDN with import maps)
- **Coordinate system**: Right-handed with Z-up orientation
- **Edge interaction**: Click edges to cycle through unknown→filledIn→ruledOut→unknown
- **Face interaction**: Click faces to highlight them (debugging feature)
- **Camera controls**: OrbitControls for 3D navigation with zoom constraints

## Current State & TODOs

The project is in active development. Key incomplete features:
- Puzzle loading from JSON data files
- Win condition detection
- Solution validation
- Multiple polyhedron support beyond cube/dodecahedron

See `ideas/TODOs.md` for detailed development roadmap.