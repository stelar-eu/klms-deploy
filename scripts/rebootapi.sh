#!/bin/bash

# Define an array for default namespaces
DEFAULT_NAMESPACES=("vista" "abaco" "agroknow")

# Function to restart deployment in a namespace
restart_namespace() {
    local namespace=$1
    echo "🚀 Restarting deployment 'stelarapi' in namespace: $namespace"
    kubectl rollout restart deployment stelarapi -n "$namespace"
    if [ $? -eq 0 ]; then
        echo "✅ Successfully restarted 'stelarapi' in $namespace."
    else
        echo "❌ Failed to restart 'stelarapi' in $namespace."
    fi
}

# Function to run make
run_make() {
    echo "🔧 Running 'make' under ~/stelar/data-api/"
    cd ~/stelar/data-api/ || { echo "❌ Could not change directory to ~/stelar/data-api/"; exit 1; }
    make
    if [ $? -eq 0 ]; then
        echo "✅ 'make' completed successfully."
    else
        echo "❌ 'make' failed."
    fi
    cd - > /dev/null
}

# Main logic
if [[ $1 == "-n" && -n $2 ]]; then
    namespace=$2
    run_make
    echo "🌟 Namespace provided: $namespace"
    restart_namespace "$namespace"
else
    echo "⚠️  No namespace provided. This will apply to default namespaces: ${DEFAULT_NAMESPACES[*]}."
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    run_make
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for namespace in "${DEFAULT_NAMESPACES[@]}"; do
            restart_namespace "$namespace"
        done
    else
        echo "🚫 Operation canceled by user."
        exit 1
    fi
fi
