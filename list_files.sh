#!/bin/bash

echo "Files in current project:" > list_files.txt
echo "=========================" >> list_files.txt
find . -not -path "*/.git/*" -not -path "*/.venv/*" -type f >> list_files.txt
