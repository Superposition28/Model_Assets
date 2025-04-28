
import bpy
import bmesh
import os
import struct
import re
import io
import math
import mathutils
import numpy as np
import string

from .helpers import log_to_blender

# Characters typically allowed in programmer-defined strings
ALLOWED_CHARS = string.ascii_letters + string.digits + '_-.'
ALLOWED_CHARS_BYTES = ALLOWED_CHARS.encode('ascii') # Convert allowed chars to bytes


# --- Adapted String Finding Function ---
def find_strings_by_signature_in_data(data: bytes, signatures_info: list, max_string_length: int, min_string_length: int, context_bytes: int, string_context_bytes: int) -> list:
    """
    Searches binary data for specific byte signatures and attempts to extract
    associated strings at a fixed relative offset.
    Outputs results including context around the signature and string.

    Args:
        data (bytes): The binary data to search within.
        signatures_info (list): A list of dictionaries, each containing 'signature'
                                ('bytes'), 'relative_string_offset' (int), and
                                'description' (str).
        max_string_length (int): Maximum number of bytes to check for a string.
        min_string_length (int): Minimum length for an extracted string to be
                                considered valid.
        context_bytes (int): Bytes of context around the signature.
        string_context_bytes (int): Bytes of context around the extracted string.

    Returns:
        list: A list of dictionaries for found patterns, containing details
            similar to the previous script's output. (Includes context/details
            even if not all are logged)
    """
    results = []
    data_len = len(data)

    # log_to_blender("[String Search] Starting search for configured fixed signatures...", to_blender_editor=False) # Console only - Too chatty

    for sig_info in signatures_info:
        signature = sig_info['signature']
        relative_string_offset = sig_info['relative_string_offset']
        signature_len = len(signature)
        current_offset = 0

        # log_to_blender(f"[String Search] Searching for signature: {signature.hex()} ('{sig_info['description']}')", to_blender_editor=False) # Console only - Too chatty

        while current_offset < data_len:
            # Search for the next occurrence of the signature
            signature_offset = data.find(signature, current_offset)

            if signature_offset == -1:
                # Signature not found further in the data
                break

            # Calculate the potential string start offset
            string_start_offset = signature_offset + relative_string_offset

            # Check if the potential string start is within data bounds
            if string_start_offset < 0 or string_start_offset >= data_len:
                # log_to_blender(f"Warning: Calculated string offset {string_start_offset:08X} for signature at {signature_offset:08X} is out of data bounds.", to_blender_editor=False) # Too chatty for console
                current_offset = signature_offset + signature_len
                continue


            # --- Attempt to extract string ---
            extracted_string_bytes = b""
            # Limit string search to not go past max_string_length OR data end
            string_search_end = min(data_len, string_start_offset + max_string_length)
            string_end_offset = string_start_offset # Initialize end offset to start

            # Ensure we don't read past the end of the data
            if string_start_offset < data_len:
                for i in range(string_start_offset, string_search_end):
                    if i >= data_len: # Extra safety check, though range should prevent this
                        break
                    byte = data[i]
                    if byte in ALLOWED_CHARS_BYTES:
                        extracted_string_bytes += bytes([byte])
                        string_end_offset = i + 1 # Update end offset (exclusive)
                    else:
                        # Non-allowed character ends the string
                        break


            extracted_string_text = None
            is_valid_string = False
            string_context_before_data = None
            string_context_after_data = None


            if extracted_string_bytes:
                try:
                    extracted_string_text = extracted_string_bytes.decode('ascii')
                    if len(extracted_string_text) >= min_string_length:
                        is_valid_string = True
                        # --- Extract context bytes around the STRING ---
                        string_context_before_start = max(0, string_start_offset - string_context_bytes)
                        string_context_after_end = min(data_len, string_end_offset + string_context_bytes)
                        string_context_before_data = data[string_context_before_start : string_start_offset]
                        string_context_after_data = data[string_end_offset : string_context_after_end]

                except UnicodeDecodeError:
                    # log_to_blender(f"Warning: UnicodeDecodeError at {string_start_offset:08X} trying to decode potential string.", to_blender_editor=False) # Too chatty for console
                    pass # String is not valid if decoding fails


            # --- Extract context bytes around the SIGNATURE ---
            context_before_start = max(0, signature_offset - context_bytes)
            context_after_end = min(data_len, signature_offset + signature_len + context_bytes)

            context_before_data = data[context_before_start : signature_offset]
            context_after_data = data[signature_offset + signature_len : context_after_end]

            results.append({
                'type': 'fixed_signature_string', # Indicate result type
                'signature_offset': signature_offset,
                'signature': signature.hex(),
                'signature_description': sig_info['description'],
                'context_before': context_before_data.hex(),
                'context_after': context_after_data.hex(),
                'string_found': is_valid_string,
                'string_offset': string_start_offset if is_valid_string else None,
                'string': extracted_string_text if is_valid_string else None,
                'string_context_before': string_context_before_data.hex() if string_context_before_data is not None else None,
                'string_context_after': string_context_after_data.hex() if string_context_after_data is not None else None
            })

            # Continue search *after* the current signature occurrence
            current_offset = signature_offset + signature_len

    # log_to_blender("[String Search] Fixed signature search complete.", to_blender_editor=False) # Console only - Too chatty
    return results

