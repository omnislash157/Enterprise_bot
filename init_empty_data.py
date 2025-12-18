"""Initialize empty data structure for CogTwin to boot with no corpus."""
import json
import os
import numpy as np

def create_empty_data():
    """Create all required empty data files for CogTwin."""

    # Create directories if they don't exist
    os.makedirs("data/corpus", exist_ok=True)
    os.makedirs("data/vectors", exist_ok=True)
    os.makedirs("data/indexes", exist_ok=True)

    # Create empty nodes.json
    with open("data/corpus/nodes.json", "w") as f:
        json.dump([], f)
    print("✓ Created data/corpus/nodes.json")

    # Create empty episodes.json
    with open("data/corpus/episodes.json", "w") as f:
        json.dump([], f)
    print("✓ Created data/corpus/episodes.json")

    # Create empty dedup_index.json
    with open("data/corpus/dedup_index.json", "w") as f:
        json.dump({}, f)
    print("✓ Created data/corpus/dedup_index.json")

    # Create empty nodes.npy (0, 1024) shape
    empty_nodes = np.empty((0, 1024), dtype=np.float32)
    np.save("data/vectors/nodes.npy", empty_nodes)
    print("✓ Created data/vectors/nodes.npy with shape (0, 1024)")

    # Create empty episodes.npy (0, 1024) shape
    empty_episodes = np.empty((0, 1024), dtype=np.float32)
    np.save("data/vectors/episodes.npy", empty_episodes)
    print("✓ Created data/vectors/episodes.npy with shape (0, 1024)")

    # Create empty clusters.json
    with open("data/indexes/clusters.json", "w") as f:
        json.dump({}, f)
    print("✓ Created data/indexes/clusters.json")

    # Create manifest.json with version and counts
    manifest = {
        "version": "1.0.0",
        "counts": {
            "nodes": 0,
            "episodes": 0,
            "clusters": 0
        },
        "created_at": "empty_init",
        "description": "Empty data structure for CogTwin"
    }
    with open("data/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print("✓ Created data/manifest.json")

    print("\n✅ All empty data files created successfully!")

if __name__ == "__main__":
    create_empty_data()
