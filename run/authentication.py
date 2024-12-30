import yaml


def authentication(userid: str) -> bool:
    with open('data/userData.yaml', 'r', encoding='utf-8') as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
    for user in data:
        if userid == user:
            return True
    return False


def delete_key(key_to_delete: str) -> bool:
    """
    删除字典中指定的键及其对应的值，并将更新后的字典写回文件。

    :param key_to_delete: 要删除的键
    :return: 是否成功删除（True/False）
    """
    try:
        # 读取 YAML 文件
        with open('data/userData.yaml', 'r', encoding='utf-8') as file:
            data = yaml.load(file, Loader=yaml.FullLoader)

        # 检查键是否存在并删除
        if key_to_delete in data:
            del data[key_to_delete]
            # 将更新后的数据写回文件
            with open('data/userData.yaml', 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True)
            print(f"Key '{key_to_delete}' has been successfully deleted.")
            return True
        else:
            print(f"Key '{key_to_delete}' not found in the data.")
            return False
    except FileNotFoundError:
        print("Error: File 'data/userData.yaml' not found.")
        return False
    except yaml.YAMLError as e:
        print(f"Error while processing YAML file: {e}")
        return False
