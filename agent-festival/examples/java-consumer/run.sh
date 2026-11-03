#!/bin/zsh
# Java conformance consumer runner: builds and runs the fixture corpus.
# Usage: ./run.sh [path-to-schema]  (default: the repo's schema/ two levels up)
set -euo pipefail
cd "$(dirname "$0")"

export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
MVN=${MVN:-mvn}

echo "== build =="
$MVN -q -DskipTests package
$MVN -q dependency:build-classpath -Dmdep.outputFile=target/cp.txt

echo "== run =="
SCHEMA_DIR="${1:-$(cd ../../schema && pwd)}"
exec "$JAVA_HOME/bin/java" -cp "target/classes:$(cat target/cp.txt)" spike.Main "$SCHEMA_DIR"
