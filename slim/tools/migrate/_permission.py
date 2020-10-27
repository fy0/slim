from dataclasses import dataclass
from typing import Dict


class A:
    QUERY = 'query'
    READ = 'read'
    WRITE = 'write'
    CREATE = 'create'
    DELETE = 'delete'

    ALL = {'query', 'read', 'write', 'create', 'delete'}


@dataclass
class Ability:
    data: Dict
    based_on: 'Ability' = None

    def __post_init__(self):
        self.allow_delete = {}
        self.default_perm: Dict[str, set] = {}
        self.append_perm: Dict[str, set] = {}

        '''
        if self.based_on:
            data_new = {}
            data_new.update(self.based_on.data)

            for table, table_perm in self.data.items():
                # 旧数据有，新数据没有，不管

                # 新数据里有，旧数据没有，直接覆盖
                if table not in data_new:
                    data_new[table] = table_perm

                # 如果同时存在，合并
                if table in self.data and table in data_new:
                    for column, perm in self.data[table].items():
                        data_new[table][column] = perm

            self.data = data_new
            self.allow_delete.update(self.based_on.allow_delete)
        '''
        for table, table_perm in self.data.items():
            if isinstance(table_perm, set):
                self.data[table] = {'|': A.ALL}

        for table, table_perm in self.data.items():
            count = 0
            if isinstance(table_perm, set):
                table_perm = {'|': A.ALL}

            append = set(table_perm.get('|', set()))

            for column, perm in table_perm.items():
                perm = set(perm)
                perm |= append
                if 'delete' in perm:
                    count += 1
                # append 只是为了测试 delete 权限，不用写回
                # table_perm[column] = perm

            if len(table_perm) == count:
                self.allow_delete[table] = True

            self.default_perm[table] = table_perm.get('*', None)
            self.append_perm[table] = table_perm.get('|', None)


def role_convert(role: Ability, name=None, based_on_name=None):
    import re
    print('from pycurd.permission import RoleDefine, TablePerm, A\n\n')

    def name_format(n):
        def pattern_callback(pat):
            r = pat.group(1)
            if r.startswith('_'):
                r = r[1:]
            return r.upper()

        return re.sub(r'(^\w|_\w)', pattern_callback, n)

    def show_perm(p):
        ret = '{'
        if 'query' in p:
            ret += 'A.QUERY, '
        if 'create' in p:
            ret += 'A.CREATE, '
        if 'read' in p:
            ret += 'A.READ, '
        if 'write' in p:
            ret += 'A.UPDATE, '

        if ret.endswith(', '):
            ret = ret[:-2]
        ret += '}'
        return ret

    if name:
        print('%s = RoleDefine({' % name)
    else:
        print('RoleDefine({')

    for k, v in role.data.items():
        cls_name = name_format(k)
        print('    %s: TablePerm({' % cls_name)

        for column, perm in v.items():
            if column in ('|', '*'):
                continue
            print('        %s.%s: %s,' % (cls_name, column, show_perm(perm)))

        print('    }', end='')
        flag = False

        if role.default_perm.get(k):
            flag = True
            print(',\n        default_perm=%s' % show_perm(role.default_perm.get(k)), end='')

        if role.append_perm.get(k):
            flag = True
            print(',\n        append_perm=%s' % show_perm(role.append_perm.get(k)), end='')

        is_end = False
        if role.allow_delete.get(k):
            if not flag:
                is_end = True
                print(', allow_delete=True),')
            else:
                flag = True
                print(',\n        allow_delete=True', end='')

        if not is_end:
            if flag:
                print('\n    ),')
            else:
                print('),')

    if role.based_on:
        print('}, based_on=%s)' % (based_on_name or '$base_name$'))
    else:
        print('})')

    print()


if __name__ == '__main__':
    # usage
    from slim.tools.migrate._permission import A, Ability, role_convert

    visitor = Ability({
        'topic': {
            'title': (A.READ,),
            'board_id': (A.QUERY, A.READ),
        }
    })

    role_convert(visitor)
