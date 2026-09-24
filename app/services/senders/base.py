from abc  import ABC ,abstractmethod
from app.models.notification import Notification
class channelSender(ABC):
     @abstractmethod 
     async def send (self,notification:Notification )->None:
          raise NotImplementedError