import { UserService } from "./UserService";
import { UserService as Service } from "./UserService";

const service = new UserService();
const anotherService = new Service();

service.getUser(1);
anotherService.getUser(2);
