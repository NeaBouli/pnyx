import { requireNativeModule } from 'expo-modules-core';

export class Identity {
    private _privateKey: Uint8Array
    constructor(privateKey: Uint8Array) {
        this._privateKey = privateKey
    }


    public commitment(): string {
        const identityModule = requireNativeModule('Identity')
        identityModule.initIdentity(this._privateKey)
        return identityModule.commitment()
    }

    public privateKey(): Uint8Array {
        const identityModule = requireNativeModule('Identity')
        identityModule.initIdentity(this._privateKey)
        return identityModule.privateKey()
    }

    public secretScalar(): string {
        const identityModule = requireNativeModule('Identity')
        identityModule.initIdentity(this._privateKey)
        return identityModule.secretScalar()
    }

    public toElement(): Uint8Array {
        const identityModule = requireNativeModule('Identity')
        identityModule.initIdentity(this._privateKey)
        return identityModule.toElement()
    }
}


export class Group {
    private _members: Uint8Array[]
    constructor(members: Uint8Array[]) {
        this._members = members
    }

    public root(): Uint8Array {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        return groupModule.root()
    }

    public depth(): number {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        return groupModule.depth()
    }

    public members(): Uint8Array[] {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        return groupModule.members()
    }

    public indexOf(member: Uint8Array): number {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        return groupModule.indexOf(Array.from(member))
    }

    public addMember(member: Uint8Array): void {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        groupModule.addMember(Array.from(member))
    }

    public addMembers(members: Uint8Array[]): void {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        const newMembersData = members.map(member => Array.from(member))
        groupModule.addMembers(newMembersData)
    }

    public updateMember(index: number, member: Uint8Array): void {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        groupModule.updateMember(index, Array.from(member))
    }

    public removeMember(index: number): void {
        const groupModule = requireNativeModule('Group')
        const membersData = this._members.map(member => Array.from(member))
        groupModule.initGroup(membersData)
        groupModule.removeMember(index)
    }

}

export async function generateSemaphoreProof(identity: Identity, group: Group, message: string, scope: string, treeDepth: number): Promise<string> {
    const proofModule = requireNativeModule('Proof')
    const privateKey = identity.privateKey()
    const membersData = group.members().map(member => Array.from(member))
    return await proofModule.generateSemaphoreProof(privateKey, membersData, message, scope, treeDepth)
}

export async function verifySemaphoreProof(proof: string): Promise<boolean> {
    const proofModule = requireNativeModule('Proof')
    return proofModule.verifySemaphoreProof(proof)
}
