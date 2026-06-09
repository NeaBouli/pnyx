package expo.modules.semaphore

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.exception.CodedException
import java.io.File
import uniffi.mopro.*

class IdentityModule : Module() {
  private var identity: Identity? = null

  override fun definition() = ModuleDefinition {
    Name("Identity")

    Function("initIdentity") { privateKey: ByteArray ->
      identity = Identity(privateKey)
    }

    Function("commitment") {
      identity?.commitment()
    }

    Function("privateKey") {
      identity?.privateKey()
    }

    Function("secretScalar") {
      identity?.secretScalar()
    }

    Function("toElement") {
      identity?.toElement()
    }
  }
}
