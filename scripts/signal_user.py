from hashids import Hashids
from bson import ObjectId
import os

# Configure Hashids
HASHIDS_SALT = os.getenv('HASHIDS_SALT', 'your-secure-salt')
HASHIDS_MIN_LENGTH = int(os.getenv('HASHIDS_MIN_LENGTH', 16))
HASHIDS_ALPHABET = os.getenv('HASHIDS_ALPHABET', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH, alphabet=HASHIDS_ALPHABET)

# Example ObjectId values (replace with your actual IDs)
object_ids = [
    '67fe36ab5caf54fdaee941bf',
    '6810bf7b0d2ca508aab00cf0',
    '6810d8f746561ec0e8831718',
    '68131cbfa8002d36b898df37',
    '68131d0ca8002d36b898df38',
    '68131d3aa8002d36b898df39',
    '68131d6ba8002d36b898df3a',
    '68131d93a8002d36b898df3b',
    '68131dd2a8002d36b898df3c',
    '68131e05a8002d36b898df3d',
    '68131e2fa8002d36b898df3e',
    '68131e6aa8002d36b898df3f',
    '68131e9ca8002d36b898df40',
    '68131ec0a8002d36b898df41',
    '68131ee2a8002d36b898df42',
    '68131effa8002d36b898df43',
    '68131f20a8002d36b898df44',
    '68131f3ea8002d36b898df45',
    '68131f5ca8002d36b898df46',
    '68131f78a8002d36b898df47',
    '68131fd0a8002d36b898df48',
    '68132019a8002d36b898df49',
    '681f1d4181c606bcef972a3d'
]

# Convert to HashIDs
hashids_list = []
for oid_str in object_ids:
    oid = ObjectId(oid_str)
    unique_int = int(oid.generation_time.timestamp() * 1000) + int(str(oid)[18:], 16)
    hashid = hashids.encode(unique_int)
    hashids_list.append({"object_id": oid_str, "hash_id": hashid})
    print(hashid)

# Print or save results
print(hashids_list)

# Optionally save to file
import json
with open('user_hashids.json', 'w') as f:
    json.dump(hashids_list, f, indent=2)
