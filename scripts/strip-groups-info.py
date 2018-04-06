import argparse


def strip_groups_info(input_file, output_file):
    with open(input_file) as fh:
        lines = [ ln.rstrip('\r\n') for ln in fh.readlines() ]

    output = []
    group_tag = False
    process_group = False
    seen_groups = False
    process_env = False
    env_tag = False
    env_opt = False
    for i in range(0, len(lines)):
        ln = lines[i].strip()
        if ln != '<group>' and not seen_groups:
            output.append(lines[i])
        if ln == '<group>':
            group_tag = True
            seen_groups = True
            continue
        if ln == '</group>':
            if process_group:
                output.append(lines[i])
                process_group = False
                continue
        if ln == '<environment>':
            env_tag = True
            continue
        if ln == '</environment>':
            if process_env:
                output.append(lines[i])
                process_env = False
                continue
        if group_tag and ln.startswith('<id>'):
            gr_id = ln[4:ln.find('<',4)]
            if gr_id in ['core', 'base']:
                process_group = True
                output.append(lines[i-1])
                output.append(lines[i])
                continue
        if env_tag and ln.startswith('<id>'):
            env_id = ln[4:ln.find('<',4)]
            if env_id in ['minimal']:
                process_env = True
                output.append(lines[i-1])
                output.append(lines[i])
                continue
        if process_group:
            skip = False
            if ln.startswith('<packagereq') and 'type="optional"' in ln:
                skip = True
            if ln.startswith('<packagereq') and 'type="conditional"' in ln:
                skip = True
            if not skip:
                output.append(lines[i])
            continue
        if process_env:
            if ln == '<optionlist>':
                env_opt = True
            elif ln == '</optionlist>':
                env_opt = True
            else:
                if not env_opt:
                    output.append(lines[i])
            continue
    output.append('</comps>')

    with open(output_file, mode='w') as fh:
        for ln in output:
            fh.writelines([ln, '\n'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    strip_groups_info(args.input, args.output)


if __name__ == '__main__':
    main()
