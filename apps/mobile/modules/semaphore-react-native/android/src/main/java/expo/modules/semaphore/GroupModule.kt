package expo.modules.semaphore

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.exception.CodedException
import java.io.File
import uniffi.mopro.*

class GroupModule : Module() {
  private var group: Group? = null

  override fun definition() = ModuleDefinition {
    Name("Group")

    Function("initGroup") { members: List<List<Int>> ->
      try {
        val membersData = members.map { member -> member.map { it.toByte() }.toByteArray() }
        group = Group(members = membersData)

      } catch (e: Exception) {
        throw CodedException("GroupInitError", e)
      }
    }

    Function("root") {
      group?.root()
    }

    Function("depth") {
      group?.depth()?.toInt() ?: 0
    }

    Function("members") {
      group?.members() ?: emptyList<ByteArray>()
    }

    Function("indexOf") { member: List<Int> ->
      group?.indexOf(member.map { it.toByte() }.toByteArray())?.toInt()
    }

    Function("addMember") { member: List<Int> ->
      group?.addMember(member.map { it.toByte() }.toByteArray())
    }

    Function("addMembers") { members: List<List<Int>> ->
      val membersData = members.map { member -> member.map { it.toByte() }.toByteArray() }
      group?.addMembers(membersData)
    }

    Function("updateMember") { index: Int, member: List<Int> ->
      group?.updateMember(index.toUInt(), member.map { it.toByte() }.toByteArray())
    }

    Function("removeMember") { index: Int ->
      group?.removeMember(index.toUInt())
    }
  }
} 