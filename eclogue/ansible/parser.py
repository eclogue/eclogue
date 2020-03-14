

def to_playbook_command(result):
    args = ['ansible-playbook']
    data = result['data']
    args.append(data['entry'])
    options = data['options']
    for k, v in options.items():
        if k == 'inventory':
            args.append(' -i [dynamic hosts]')
            continue
        if v:
            item = '--' + k + ' '
            if type(v) == list:
                item += ','.join(v)
            else:
                item += str(v)
            args.append(item)
    return ' '.join(args)


