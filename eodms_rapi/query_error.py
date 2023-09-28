class QueryError:
    """
    The QueryError class is used to store error information for a query.
    """

    def __init__(self, msgs):
        """
        Initializer for QueryError object which stores an error message.
        
        :param msgs: The error message to print.
        :type  msgs: str
        """

        self.msgs = msgs

    def get_msgs(self, as_str=False):
        """
        Gets the messages stored with the QueryError.
        
        :param as_str: Determines whether to return a string or a list of
        messages.
        :type  as_str: boolean
        
        :return: Either a string or a list of messages.
        :rtype: str or list
        """

        if as_str:
            if isinstance(self.msgs, list):
                return ' '.join(filter(None, self.msgs))

        return self.msgs

    def _set_msgs(self, msgs):
        """
        Sets the messages stored with the QueryError.
        
        :param msgs: Can either be a string or a list of messages.
        :type  msgs: str or list
        
        """
        self.msgs = msgs