import express from "express";

class UserService {
    constructor() {
        this.name = "ArchLens";
    }

    getUser() {
        return this.name;
    }
}

function startServer() {
    const app = express();
    const service = new UserService();
    service.getUser();
}

const greet = (name) => {
    return "Hello " + name;
};

// Multiple parameters
function add(a, b) {
    return a + b;
}

// Default parameter
function greetUser(name = "User") {
    return "Hello " + name;
}

// Rest parameter
function sum(...numbers) {
    return numbers.reduce((total, number) => total + number, 0);
}

// Anonymous arrow function
const multiply = (a, b) => a * b;

// Nested function
function outer() {
    function inner(value) {
        return value;
    }

    return inner(10);
}
