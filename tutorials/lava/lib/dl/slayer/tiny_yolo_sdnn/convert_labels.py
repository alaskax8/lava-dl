import json
import os
import argparse
import sys

def convert_label_format(source_data, input_filename_for_error_context, start_id=1):
    """
    Converts a single image's label data from Label Studio format 
    to the target format. Derives internal 'name' and 'videoName' 
    fields from the 'task.data.image' path within source_data.

    Args:
        source_data (dict): The loaded JSON data from the source file.
        input_filename_for_error_context (str): Original source filename for logging context.
        start_id (int): The starting integer for generating sequential label IDs.

    Returns:
        list: A list containing a single dictionary representing the 
              converted frame data in the target format, or None if 
              conversion fails.
    """
    
    # Basic validation of source data structure before accessing keys
    if "task" not in source_data or "data" not in source_data["task"] or \
       "image" not in source_data["task"]["data"] or "result" not in source_data:
        print(f"  Error ({input_filename_for_error_context}): Source JSON structure is missing required keys ('task', 'data', 'image', 'result').")
        return None
        
    # --- Extract Filename and VideoName from source_data ---
    try:
        # Get the image path stored in the Label Studio JSON
        image_path_in_json = source_data["task"]["data"]["image"]
        # Extract the actual filename (e.g., "image001.png", "photo.jpg")
        actual_image_filename = os.path.basename(image_path_in_json) 
        # Get the base filename without extension (e.g., "image001", "photo")
        base_image_filename = os.path.splitext(actual_image_filename)[0] 
        # Use the base image filename as the 'videoName' for consistency
        video_name = base_image_filename 
    except KeyError as e:
        # Should ideally be caught before calling this function now, but keep as safety net
        print(f"  Error ({input_filename_for_error_context}): Could not extract 'task.data.image' key: {e}")
        return None
    except Exception as e:
         print(f"  Error ({input_filename_for_error_context}): Processing image path from JSON failed: {e}")
         return None

    # --- Handle cases with no annotations ("result" is empty) ---
    if not source_data["result"]:
        print(f"  Warning ({input_filename_for_error_context}): Source JSON has an empty 'result' list. Creating output with empty labels.")
        # Proceed to create the structure but with an empty labels list
        converted_labels = []
        original_width = None # No dimensions available/needed if no labels
        original_height = None
    else:
        # --- Get Image Dimensions (only needed if there are results) ---
        original_width = None
        original_height = None
        try:
            first_annotation = source_data["result"][0]
            original_width = first_annotation["original_width"]
            original_height = first_annotation["original_height"]
        except (KeyError, IndexError) as e:
            print(f"  Error ({input_filename_for_error_context}): Could not extract image dimensions from the first annotation. Error: {e}")
            return None # Cannot process labels without dimensions

        converted_labels = []
        label_counter = start_id

        # --- Process Annotations ---
        for idx, annotation in enumerate(source_data["result"]):
            annotation_id_for_error = annotation.get('id', f'index_{idx}')
            try:
                # Redundant check, but safe: Ensure dimensions were found
                if original_width is None or original_height is None:
                     print(f"  Error ({input_filename_for_error_context}): Internal error - Missing image dimensions needed to process annotations.")
                     return None # Should have been caught earlier

                value = annotation["value"]
                
                # Get Category
                if not value.get("rectanglelabels") or not isinstance(value["rectanglelabels"], list) or len(value["rectanglelabels"]) == 0:
                     print(f"  Warning ({input_filename_for_error_context}): Skipping annotation '{annotation_id_for_error}': Missing or empty 'rectanglelabels'.")
                     continue 
                category = value["rectanglelabels"][0]

                # Calculate Absolute Bbox Coordinates
                x_rel = value["x"]
                y_rel = value["y"]
                width_rel = value["width"]
                height_rel = value["height"]

                x1 = (x_rel / 100.0) * original_width
                y1 = (y_rel / 100.0) * original_height
                x2 = ((x_rel + width_rel) / 100.0) * original_width
                y2 = ((y_rel + height_rel) / 100.0) * original_height
                
                # Generate Target Label ID
                label_id = f"{label_counter:08d}" 
                label_counter += 1

                # Set Attributes (Defaults)
                attributes = {"occluded": False, "truncated": False, "crowd": False}

                # Assemble Box2D
                box2d = {"x1": x1, "x2": x2, "y1": y1, "y2": y2}
                
                # Create final label dictionary
                converted_labels.append({
                    "id": label_id, "category": category,
                    "attributes": attributes, "box2d": box2d
                })

            except KeyError as e:
                print(f"  Warning ({input_filename_for_error_context}): Skipping annotation '{annotation_id_for_error}' due to missing key: {e}")
                continue 
            except Exception as e:
                 print(f"  Warning ({input_filename_for_error_context}): Skipping annotation '{annotation_id_for_error}' due to unexpected error: {e}")
                 continue 

    # --- Assemble the final frame structure ---
    target_frame = {
        # Use the actual image filename extracted from the source JSON's 'image' field
        "name": actual_image_filename, 
        "labels": converted_labels,
        # Use the video name derived from the base image filename
        "videoName": video_name, 
        "frameIndex": 0 
    }

    return [target_frame] # Return list containing the single frame

# --- Main execution logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Label Studio JSON files from an input directory to the target video frame format. "
                    "Output JSON filename is based on the image path specified *inside* the source JSON."
    )
    parser.add_argument("input_dir", help="Directory containing input Label Studio JSON files.")
    parser.add_argument("output_dir", help="Directory to save converted JSON files (named after image, with .json suffix).")
    parser.add_argument("--start_id", type=int, default=1, 
                        help="Starting integer for sequential label IDs (restarts for each file).")

    args = parser.parse_args()

    # --- Validate Directories ---
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' not found or is not a directory.")
        sys.exit(1)
    try:
        os.makedirs(args.output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create output directory '{args.output_dir}'. Error: {e}")
        sys.exit(1)

    # --- Process Files ---
    success_count = 0
    fail_count = 0
    skipped_count = 0
    total_entries_in_dir = 0

    print(f"Starting conversion from '{args.input_dir}' to '{args.output_dir}'...")

    for entry_name in os.listdir(args.input_dir):
        total_entries_in_dir += 1
        input_path = os.path.join(args.input_dir, entry_name)

        if not os.path.isfile(input_path):
            # print(f"Skipping '{entry_name}': Not a file.") # Optional logging
            skipped_count += 1
            continue 

        print(f"Processing source file '{entry_name}'...")
        
        source_json_data = None
        output_path = None
        output_filename = None # Initialize

        # Read JSON and determine output filename based on its content
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                source_json_data = json.load(f)
            
            # Extract image info needed for output filename determination
            # Check necessary keys exist before trying to access them
            if "task" not in source_json_data or "data" not in source_json_data["task"] or \
               "image" not in source_json_data["task"]["data"]:
                 raise KeyError("Required key path 'task.data.image' missing in JSON.")

            image_path_in_json = source_json_data['task']['data']['image']
            actual_image_filename = os.path.basename(image_path_in_json)
            base_image_filename = os.path.splitext(actual_image_filename)[0]
            
            # Construct output filename and path based on image name derived from JSON content
            output_filename = base_image_filename + ".json" 
            output_path = os.path.join(args.output_dir, output_filename)

        except json.JSONDecodeError:
            print(f"  Error: Could not decode JSON from '{entry_name}'. Skipping.")
            fail_count += 1
            continue 
        except KeyError as e:
             print(f"  Error: {e} in '{entry_name}'. Cannot determine output filename. Skipping.")
             fail_count += 1
             continue
        except Exception as e:
            print(f"  Error reading file '{entry_name}' or extracting image path: {e}. Skipping.")
            fail_count += 1
            continue

        # --- Perform Conversion ---
        # Pass the original source filename ('entry_name') for context in logs inside the function
        converted_data = convert_label_format(source_json_data, entry_name, args.start_id) 

        # --- Save Output ---
        if converted_data:
            try:
                # Save to the path determined using image name from JSON content
                with open(output_path, 'w', encoding='utf-8') as f: 
                    json.dump(converted_data, f, indent=2) 
                success_count += 1
                # More informative success message showing the mapping
                print(f"  Successfully converted '{entry_name}' -> '{output_filename}'") 
            except IOError as e:
                print(f"  Error: Could not write output file '{output_filename}'. Error: {e}")
                fail_count += 1
            except Exception as e:
                print(f"  Error writing output file '{output_filename}': {e}")
                fail_count += 1
        else:
            # convert_label_format already printed detailed reasons for returning None
            print(f"  Conversion failed for '{entry_name}'. See previous warnings/errors.")
            fail_count += 1

    # --- Print Summary ---
    print("-" * 30)
    print("Conversion Summary:")
    print(f"  Total entries scanned in input directory: {total_entries_in_dir}")
    print(f"  Skipped (not files): {skipped_count}")
    files_attempted = total_entries_in_dir - skipped_count
    print(f"  Files processed: {files_attempted}")
    print(f"  Successful conversions: {success_count}")
    print(f"  Failed/Skipped conversions: {fail_count}")
    # Sanity check: success_count + fail_count should equal files_attempted if logic is sound
    if success_count + fail_count != files_attempted:
         print("  Warning: Mismatch in processed file counts.") 
    print(f"Output files are located in: '{args.output_dir}'")
    print("-" * 30)