#!/usr/bin/env python3
import re
import argparse
import sys
import os

def parse_kicad_pcb(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)

    # 1. ネットリスト抽出
    nets = {}
    for match in re.finditer(r'\(\s*net\s+(\d+)\s+"([^"]+)"\s*\)', content):
        nets[int(match.group(1))] = match.group(2)

    # 2. コンポーネント抽出
    components = {}
    fp_matches = list(re.finditer(r'\(\s*footprint\s+', content))

    for i, match in enumerate(fp_matches):
        start = match.start()
        end = fp_matches[i+1].start() if i+1 < len(fp_matches) else len(content)
        block = content[start:end]

        # Ref取得
        ref_match = re.search(r'\(fp_text\s+reference\s+"([^"]+)"', block)
        ref = ref_match.group(1) if ref_match else "Unknown"
        
        # Name取得
        name_match = re.search(r'\(footprint\s+"([^"]+)"', block)
        fp_name = name_match.group(1) if name_match else "Unknown"

        # 【自動補正】RefがUnknownなら、フットプリント名をIDとして使う
        if ref == "Unknown" or ref == "REF**":
            ref = fp_name

        # パッド解析
        pads = {}
        pad_iter = re.finditer(r'\(\s*pad\s+"?([^"\s]+)"?.*?\(\s*net\s+(\d+)\s', block, re.DOTALL)
        for pm in pad_iter:
            pads[pm.group(1)] = int(pm.group(2))
        
        # 重複回避
        original_ref = ref
        count = 1
        while ref in components:
            ref = f"{original_ref}_{count}"
            count += 1

        components[ref] = {
            "name": fp_name,
            "pads": pads,
            "pad_count": len(pads)
        }

    return nets, components

def find_component_by_query(query, components):
    """
    指定された文字列(query)でコンポーネントをあいまいに検索する
    完全一致 > 部分一致 の順で探す
    """
    # 1. 完全一致
    if query in components:
        return query
    
    # 2. 部分一致 (大文字小文字無視)
    matches = [key for key in components.keys() if query.lower() in key.lower()]
    
    if len(matches) == 1:
        return matches[0] # 1つだけ見つかればそれを返す
    elif len(matches) > 1:
        print(f"Error: Ambiguous name '{query}'. Matches: {matches}")
        sys.exit(1)
    else:
        print(f"Error: Component '{query}' not found.")
        sys.exit(1)

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def generate_markdown(nets, components, key_a, key_b):
    comp_a = components[key_a]
    comp_b = components[key_b]

    print(f"Generating Pinout: {key_a} <--> {key_b}\n")
    print(f"| {key_a} Pin | Net Name | {key_b} Pin |")
    print("| :--- | :--- | :--- |")

    sorted_pins = sorted(comp_a['pads'].keys(), key=natural_sort_key)

    for pin_a in sorted_pins:
        net_id = comp_a['pads'][pin_a]
        net_name = nets.get(net_id, "NC")

        connected_pins_b = []
        if net_id != 0:
             connected_pins_b = [p for p, nid in comp_b['pads'].items() if nid == net_id]
        
        pin_b_str = ", ".join(sorted(connected_pins_b, key=natural_sort_key)) if connected_pins_b else "-"
        
        print(f"| {pin_a} | {net_name} | {pin_b_str} |")

def main():
    parser = argparse.ArgumentParser(description="KiCad Pinout Generator (Fuzzy Match Supported)")
    parser.add_argument("file", help="Input .kicad_pcb file")
    parser.add_argument("-l", "--list", action="store_true", help="List all components")
    parser.add_argument("-a", "--comp-a", help="Reference or partial name for Component A")
    parser.add_argument("-b", "--comp-b", help="Reference or partial name for Component B")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.")
        sys.exit(1)

    nets, components = parse_kicad_pcb(args.file)

    if args.list or (not args.comp_a and not args.comp_b):
        print(f"--- Components in {args.file} ---")
        print(f"{'Ref / ID':<40} {'Pads':<6}")
        print("-" * 50)
        for ref, data in components.items():
            # 長すぎる名前は表示上省略するが、検索はフルネームで可能
            disp_ref = (ref[:37] + '..') if len(ref) > 37 else ref
            print(f"{disp_ref:<40} {data['pad_count']:<6}")
        print("-" * 50)
        return

    if args.comp_a and args.comp_b:
        # あいまい検索でキーを特定
        key_a = find_component_by_query(args.comp_a, components)
        key_b = find_component_by_query(args.comp_b, components)
        
        generate_markdown(nets, components, key_a, key_b)
    else:
        print("Error: Specify both -a and -b.")

if __name__ == "__main__":
    main()