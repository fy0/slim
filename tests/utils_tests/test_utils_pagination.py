from slim.utils import pagination_calc


def test_pagination():
    pg = pagination_calc(1000, 10, cur_page=1)
    assert pg['cur_page'] == 1
    assert pg['prev_page'] is None
    assert pg['next_page'] == 2

    assert pg['first_page'] is None
    assert pg['last_page'] == 100
    assert pg['numbers'] == [1, 2, 3, 4, 5]
    assert pg['info']['page_size'] == 10
    assert pg['info']['page_count'] == 100
    assert pg['info']['items_count'] == 1000

    pg = pagination_calc(1000, 10, cur_page=2)
    assert pg['cur_page'] == 2
    assert pg['prev_page'] == 1
    assert pg['next_page'] == 3

    assert pg['first_page'] is None
    assert pg['last_page'] == 100
    assert pg['numbers'] == [1, 2, 3, 4, 5]
    assert pg['info']['page_size'] == 10
    assert pg['info']['page_count'] == 100
    assert pg['info']['items_count'] == 1000

    pg = pagination_calc(1000, 10, cur_page=4)
    assert pg['cur_page'] == 4
    assert pg['prev_page'] == 3
    assert pg['next_page'] == 5

    assert pg['first_page'] == 1
    assert pg['last_page'] == 100
    assert pg['numbers'] == [2, 3, 4, 5, 6]
    assert pg['info']['page_size'] == 10
    assert pg['info']['page_count'] == 100
    assert pg['info']['items_count'] == 1000


if __name__ == '__main__':
    test_pagination()
