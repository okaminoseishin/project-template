class Namespace(dict):
    """
    Makes possible to access (nested) dict keys as attributes.

    Has four drawbacks:
    - uses recursion, so not recommended for heavily volatile structures
    - dict attributes will be silently ignored and not replaced by value
    - invalid python identifiers can be accessed only with `getattr` function
    - missing attribute (key) returned as empty namespace object. So using

    ```python
    if namespace.missing:
        <do some stuff>
    ```
    is valid, but

    ```python
    if namespace.missing == 5:
        <do some stuff>
    ```
    results in `TypeError`. Also `hasattr` always return True.
    """

    def __init__(self, *iterable, **kwargs):
        for key, value in dict(*iterable, **kwargs).items():
            setattr(self, key, value)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __getattr__(self, name):
        name = name.split('.')

        for path in name:
            if path not in self.keys():
                setattr(self, path, self.__class__())
            if path is not name[-1]:
                self = getattr(self, path)

        return super().__getattribute__(name[-1])

    def __setattr__(self, name, value):
        name, value = name.split('.'), self.__morph__(value)

        for path in name[:-1]:
            self = getattr(self, path)

        if name[-1] not in self.__class__.__dict__:
            super().__setattr__(name[-1], value)
        super().__setitem__(name[-1], value)

    def __morph__(self, object: object):
        # immediately return strings and bytes-like
        if isinstance(object, (bytes, str)):
            return object
        # any mapping will be converted immediately
        if hasattr(object, "keys") and hasattr(object, "__getitem__"):
            return self.__class__(object)
        # any mapping in sequence will be converted
        if hasattr(object, "__iter__") or hasattr(object, "__getitem__"):
            # apply to mutable sequences only
            if hasattr(object, "__setitem__"):
                # morphs items on assignment
                class Sequence(object.__class__):
                    def __setitem__(instance, index, value):
                        super().__setitem__(index, self.__morph__(value))
                return Sequence((
                    self.__morph__(item) for item in object))
            # apply to immutables
            return object.__class__((
                self.__morph__(item) for item in object))
        return object

    def update(self, *iterable, **kwargs):
        for key, value in type(self)(*iterable, **kwargs).items():
            if isinstance(value, type(self)):   # TODO: check if required
                if isinstance(self[key], type(self)):
                    self[key].update(value)
            else:
                self[key] = value
