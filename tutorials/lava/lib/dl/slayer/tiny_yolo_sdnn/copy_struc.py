import os
import json
import shutil
import random
import argparse
import sys

# get_info_from_json function remains the same
def get_info_from_json(annotation_path):
    """
    Reads the image filename ("name") and videoName from the specific 
    JSON structure created by the first script.

    Args:
        annotation_path (str): Path to the .json annotation file.

    Returns:
        tuple (str, str) or (None, None): (image_filename, videoName) on success,
                                          (None, None) on error.
    """
    try:
        with open(annotation_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            image_filename = data[0].get("name") 
            video_name = data[0].get("videoName")
            
            missing_keys = []
            if not image_filename:
                 missing_keys.append("'name' (image filename)")
            if not video_name:
                 missing_keys.append("'videoName'")

            if missing_keys:
                print(f"  Error: Required key(s) {', '.join(missing_keys)} not found or empty in first object of JSON: {annotation_path}")
                return None, None
            else:
                 return str(image_filename), str(video_name) 
        else:
            print(f"  Error: Unexpected JSON structure in {annotation_path}. Expected a list containing at least one dictionary.")
            return None, None
    except json.JSONDecodeError:
        print(f"  Error: Could not decode JSON from {annotation_path}")
        return None, None
    except FileNotFoundError:
         print(f"  Error: Annotation file not found: {annotation_path}")
         return None, None
    except Exception as e:
        print(f"  Error reading info from {annotation_path}: {e}")
        return None, None

def main():
    parser = argparse.ArgumentParser(
        description="Split data into train/test sets. Images go into 'images/<videoName>/' folders. "
                    "Labels go into flat 'labels/' folder, renamed to '<videoName>.json' (potential overwrites)."
    )
    parser.add_argument(
        "--image_dir", 
        required=True, 
        help="Path to the directory containing the original images (e.g., ./images)."
    )
    parser.add_argument(
        "--annotation_dir", 
        required=True, 
        help="Path to the directory containing the converted .json annotation files (e.g., ./annotations)."
    )
    parser.add_argument(
        "--output_dir", 
        required=True, 
        help="Base path for the structured output (e.g., ./data_structured). Will contain 'train/images', 'train/labels', etc."
    )
    parser.add_argument(
        "--split_ratio", 
        type=float, 
        default=0.8, 
        help="Proportion of data for the training set (e.g., 0.8 for 80%). Default is 0.8."
    )
    parser.add_argument(
        "--seed", 
        type=int, 
        default=42, 
        help="Random seed for shuffling to ensure reproducible splits. Default is 42."
    )

    args = parser.parse_args()

    # --- Validate Inputs ---
    if not os.path.isdir(args.image_dir):
        print(f"Error: Image directory not found: {args.image_dir}")
        sys.exit(1)
    if not os.path.isdir(args.annotation_dir):
        print(f"Error: Annotation directory not found: {args.annotation_dir}")
        sys.exit(1)
    if not 0 < args.split_ratio < 1:
        print(f"Error: split_ratio must be between 0 and 1 (exclusive), got {args.split_ratio}")
        sys.exit(1)
        
    random.seed(args.seed)
    print(f"Using random seed: {args.seed}")

    # --- Find Image-Annotation Pairs ---
    # (This part remains unchanged)
    print("\nScanning annotations and searching for corresponding images...")
    found_pairs = []
    missing_images_count = 0
    json_errors_count = 0
    processed_annotations = 0

    annotation_files = [f for f in os.listdir(args.annotation_dir) if f.endswith('.json')]
    
    if not annotation_files:
        print(f"Error: No '.json' annotation files found in '{args.annotation_dir}'.")
        sys.exit(1)

    print(f"Found {len(annotation_files)} potential annotation files.")

    for ann_filename in annotation_files:
        processed_annotations += 1
        ann_path = os.path.join(args.annotation_dir, ann_filename)
        image_filename_from_json, video_name = get_info_from_json(ann_path)

        if image_filename_from_json and video_name:
            image_path = os.path.join(args.image_dir, image_filename_from_json)
            if os.path.isfile(image_path):
                found_pairs.append({
                    "image_path": image_path,                    
                    "annotation_path": ann_path,                 
                    "video_name": video_name, # Needed for image subdir and label renaming
                    "image_filename": image_filename_from_json,  
                    "annotation_filename": ann_filename # Original annotation filename (for context)
                })
            else:
                missing_images_count += 1
                print(f"  Warning: Image '{image_path}' (specified in '{ann_filename}') not found in image directory.")
        else:
            json_errors_count += 1
            print(f"  -> Skipping pair associated with '{ann_filename}' due to JSON read error.")
            
    # --- Report Pairing Results ---
    # (This part remains unchanged)
    print("\nPairing Scan Complete:")
    print(f"  Annotations processed: {processed_annotations}")
    print(f"  Valid image-annotation pairs found: {len(found_pairs)}")
    if missing_images_count > 0:
        print(f"  Annotations pointing to missing images: {missing_images_count}")
    if json_errors_count > 0:
        print(f"  Annotations with read errors (videoName or image filename): {json_errors_count}")

    if not found_pairs:
        print("\nError: No valid image-annotation pairs found. Cannot proceed with splitting.")
        sys.exit(1)

    # --- Shuffle and Split ---
    # (This part remains unchanged)
    print(f"\nShuffling {len(found_pairs)} pairs...")
    random.shuffle(found_pairs)
    split_index = int(len(found_pairs) * args.split_ratio)
    train_pairs = found_pairs[:split_index]
    test_pairs = found_pairs[split_index:]
    print(f"Splitting into {len(train_pairs)} training pairs ({args.split_ratio*100:.1f}%) and {len(test_pairs)} testing pairs ({(1-args.split_ratio)*100:.1f}%).")

    # --- Create Output Structure and Copy Files ---
    print(f"\nCreating output structure under '{args.output_dir}' and copying files...")
    copy_errors = 0
    overwrite_warnings = 0

    # Create the base train/test directories and their top-level image/label subdirs upfront
    for split in ['train', 'test']:
        # No need to create images subdir here, videoName folders go directly inside train/test/images
        # os.makedirs(os.path.join(args.output_dir, split, 'images'), exist_ok=True) 
        os.makedirs(os.path.join(args.output_dir, split, 'labels'), exist_ok=True)

    for split_name, pairs in [('train', train_pairs), ('test', test_pairs)]:
        print(f"  Processing '{split_name}' set ({len(pairs)} pairs)...")
        split_copy_count = 0
        split_error_count = 0
        
        # Define the target directory for labels for this entire split
        target_label_dir = os.path.join(args.output_dir, split_name, 'labels')
        # Define the base directory for images for this entire split
        target_images_base_dir = os.path.join(args.output_dir, split_name, 'images')
        # Ensure the base images dir exists
        os.makedirs(target_images_base_dir, exist_ok=True) 


        for pair in pairs:
            try:
                # --- Target Paths ---
                # 1. Image Path: Goes into a subdirectory named after videoName
                target_image_video_dir = os.path.join(target_images_base_dir, pair['video_name'])
                os.makedirs(target_image_video_dir, exist_ok=True) # Create specific video folder for image
                target_image_path = os.path.join(target_image_video_dir, pair['image_filename']) 
                
                # 2. Annotation Path: Goes into the flat labels directory, renamed to videoName.json
                new_annotation_filename = pair['video_name'] + ".json" 
                target_annotation_path = os.path.join(target_label_dir, new_annotation_filename) 

                # --- Check for potential label overwrite before copying label ---
                if os.path.exists(target_annotation_path):
                    print(f"    Warning: Overwriting existing label file '{target_annotation_path}' (VideoName: {pair['video_name']})")
                    overwrite_warnings += 1

                # --- Copy Files ---
                shutil.copy2(pair['image_path'], target_image_path)           # Copy image to images/<videoName>/
                shutil.copy2(pair['annotation_path'], target_annotation_path) # Copy label to labels/, renaming implicitly

                split_copy_count += 1
            except Exception as e:
                # Use original annotation filename for error reporting context
                print(f"    ERROR processing annotation '{pair['annotation_filename']}' (image: '{pair['image_filename']}'): {e}")
                split_error_count += 1
                copy_errors += 1
        print(f"  Finished processing '{split_name}': {split_copy_count} pairs copied, {split_error_count} errors.")


    # --- Final Summary ---
    # (This part remains unchanged)
    print("\nScript Finished.")
    print("-" * 30)
    print("Summary:")
    print(f"  Total valid pairs found: {len(found_pairs)}")
    print(f"  Training pairs created: {len(train_pairs)}")
    print(f"  Testing pairs created: {len(test_pairs)}")
    print(f"  Total copy errors: {copy_errors}")
    if overwrite_warnings > 0:
        print(f"  Label file overwrite warnings: {overwrite_warnings} (Due to duplicate videoNames per split)")
    print(f"  Output structure created in: '{args.output_dir}'")
    print("-" * 30)


if __name__ == "__main__":
    main()