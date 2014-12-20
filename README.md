xtcp
====

xiaoyintong tcp server

Demo
----

```python
    python main.py
```

``client.py`` content:

```python
    if __name__ == "__main__":
        import logging
        logging.basicConfig(level=logging.DEBUG)

        def handler_response(message):
            return "--------{}--------".format(message)
        client = XTCPClient()

        # test1
        context = Context("localhost", 8001)
        context.concat("toupper", "xiaoxiao", handler_response)
        name = client.acquire(context)
        logging.warn("name: {}".format(name))

        # test2
        context = Context("localhost", 8001)
        context.concat("toupper", "wo men dou shi hao hai zi", handler_response)
        name2 = client.acquire(context)
        logging.warn("name2: {}".format(name2))
```

Run: `` python client.py``

Return:

```python
    INFO:root:name: --------XIAOXIAO--------
    INFO:root:name2: --------WO MEN DOU SHI HAO HAI ZI--------
```


说明
----

通讯协议：
``request_method_len``\r\n``request_method``\r\n``request_params_len``\r\n``request_params``\r\n\r\n

- 结束符： ``\r\n\r\n``
- 分割符：``\r\n``

远程调用： ``request_method(request_params)``

版本变化
-------

- 0.2.0: 添加XTCPClient，优化代码结构
- 0.1.0: 添加服务器端异常处理，处理解析数据超时

