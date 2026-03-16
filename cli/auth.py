import os
import hashlib
from getpass import getpass
from dotenv import load_dotenv

def local_auth():
    """
    Checks if a local developer passphrase is provided correctly 
    per Protocol 0 (Zero-Trust).
    In a real scenario, the hash should be stored in .env.
    """
    load_dotenv()
    
    # Normally, dev creates this hash manually and adds to .env
    # e.g. python -c "import hashlib; print(hashlib.sha256('mypass'.encode()).hexdigest())"
    expected_hash = os.getenv("BLAST_DEV_PASSPHRASE_HASH")
    
    # If not set, let's allow it but warn, or we can strictly deny. Let's deny to be strict.
    if not expected_hash:
        print("ERROR: BLAST_DEV_PASSPHRASE_HASH not set in .env")
        return False
        
    password = getpass("Developer Passphrase: ")
    hashed_input = hashlib.sha256(password.encode()).hexdigest()
    
    return hashed_input == expected_hash
