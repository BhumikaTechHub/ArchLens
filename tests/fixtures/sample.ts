interface User {
    id: number;
    name: string;
}

interface Admin {
    deleteUser(id: number): void;
}

class UserService {
    getUser(id: number): User {
        return {
            id: id,
            name: "Ayush"
        };
    }
}

function greet(name: string, age: number): string {
    return `Hello ${name}`;
}

const add = (a: number, b: number): number => a + b;

class AdminService extends UserService implements Admin {
    deleteUser(id: number): void {
        console.log("Deleting user", id);
    }
}
