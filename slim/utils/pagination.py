import math


def pagination_calc(items_count, page_size, cur_page=1, nearby=2):
    """
    :param nearby:
    :param items_count: count of all items
    :param page_size: size of one page
    :param cur_page: current page number, accept string digit
    :return: num of pages, an iterator
    """
    if type(cur_page) == str:
        # noinspection PyUnresolvedReferences
        cur_page = int(cur_page) if cur_page.isdigit() else 1
    elif type(cur_page) == int:
        if cur_page <= 0:
            cur_page = 1
    else:
        cur_page = 1

    page_count = 1 if page_size == -1 else int(math.ceil(items_count / page_size))
    items_length = nearby * 2 + 1

    # if first page in page items, first_page is None,
    # it means the "go to first page" button should not be available.
    first_page = None
    last_page = None

    prev_page = cur_page - 1 if cur_page != 1 else None
    next_page = cur_page + 1 if cur_page != page_count else None

    if page_count <= items_length:
        number_items = range(1, page_count + 1)
    elif cur_page <= nearby:
        # start of items
        number_items = range(1, items_length + 1)
        last_page = True
    elif cur_page >= page_count - nearby:
        # end of items
        number_items = range(page_count - items_length + 1, page_count + 1)
        first_page = True
    else:
        number_items = range(cur_page - nearby, cur_page + nearby + 1)
        first_page, last_page = True, True

    if first_page:
        first_page = 1
    if last_page:
        last_page = page_count

    return {
        'cur_page': cur_page,
        'prev_page': prev_page,
        'next_page': next_page,

        'first_page': first_page,
        'last_page': last_page,
        'numbers': list(number_items),

        'info': {
            'page_size': page_size,  # 分页大小
            'page_count': page_count,  # 页数
            'items_count': items_count,  # 总项个数
        }
    }
