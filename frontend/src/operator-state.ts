import { createContext, useContext } from "react";
export const validUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export const OperatorContext = createContext({ personId: "", save: (_value: string) => { void _value; } });
export const useOperator = () => useContext(OperatorContext);
